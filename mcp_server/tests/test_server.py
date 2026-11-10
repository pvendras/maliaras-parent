from datetime import date

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server import ProxyTokenVerifier, create_server
from service import LessonService, SecretClient

TOKEN = 'test-only-token-' * 4


class FakeERP:
    instances = []

    def __init__(self, student):
        self.student = student
        self.calls = []
        self.__class__.instances.append(self)

    def login(self):
        self.calls.append('login')

    def get(self, path):
        self.calls.append(path)
        if path == '/api/defaultYear':
            return {'id': 1, 'name': 'test-year'}
        if path == '/api/eclass/mylessons/1':
            return [{'id': 10, 'lesson': {'name': 'ΓΛΩΣΣΑ'}},
                    {'id': 20, 'lesson': {'name': 'ΜΑΘΗΜΑΤΙΚΑ'}}]
        if path == '/api/eclass/lesson_schedule/10':
            return {'lessons': [
                {'date': '2020-01-02', 'name': 'a', 'fornextime': 'page 7', 'private': 'hidden'},
                {'date': '2020-01-02', 'name': 'b'},
                {'date': '2020-01-01', 'name': 'old'},
                {'date': '2999-01-01', 'name': 'future'}]}
        if path == '/api/eclass/lesson_schedule/20':
            return {'lessons': [{'date': '2020-01-01', 'name': 'math'}]}
        raise AssertionError(path)


@pytest.fixture
def service():
    FakeERP.instances.clear()
    return LessonService(FakeERP)


def test_report_one_day_and_projection(service):
    result = service.fetch('anna', 'report')
    assert result['date'] == '2020-01-02'
    assert result['student_name'] == 'Άννα'
    assert len(result['subjects'][0]['entries']) == 2
    assert 'private' not in result['subjects'][0]['entries'][0]
    assert result['subjects'][1]['entries'] == []
    assert FakeERP.instances[0].calls.count('login') == 1


def test_subject_and_missing_date(service):
    result = service.fetch('nikos', 'subject', subject='γλώσσα')
    assert result['student_name'] == 'Νίκος'
    assert len(result['subjects']) == 1
    missing = service.fetch('anna', 'report', date(2020, 2, 1))
    assert missing['date'] == '2020-02-01'
    assert missing['has_entries'] is False
    assert service.fetch('anna', 'subject', subject='')['error']
    assert service.fetch('anna', 'subject', subject='unknown')['error']


def test_secret_login_and_isolation(monkeypatch):
    for student in ('anna', 'nikos'):
        prefix = f'MALIARAS_{student.upper()}'
        monkeypatch.setenv(prefix + '_USERNAME', student)
        monkeypatch.setenv(prefix + '_PASSWORD', 'fake-password')
    calls = []
    monkeypatch.setattr(SecretClient, '_request', lambda self, path, payload: calls.append((self.student, path, payload)))
    a, b = SecretClient('anna'), SecretClient('nikos')
    a.login()
    b.login()
    assert a.cookies is not b.cookies
    assert [call[2]['username'] for call in calls] == ['anna', 'nikos']
    monkeypatch.delenv('MALIARAS_ANNA_PASSWORD')
    with pytest.raises(RuntimeError, match='Missing Kubernetes'):
        a.login()
    assert len(calls) == 2


async def test_tools_and_validation(service):
    async with Client(create_server(service, TOKEN)) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == {'list_subjects', 'get_report', 'get_subject_lessons'}
        for tool in tools:
            assert 'student' in tool.inputSchema['required']
            assert tool.inputSchema['properties']['student']['enum'] == ['anna', 'nikos']
        result = await client.call_tool('get_report', {'student': 'anna'})
        assert result.data['date'] == '2020-01-02'
        before = len(FakeERP.instances)
        for arguments in ({}, {'student': 'other'}, {'student': 'anna', 'lesson_date': 'not-a-date'}):
            with pytest.raises(ToolError):
                await client.call_tool('get_report', arguments)
        assert len(FakeERP.instances) == before


async def test_markdown_is_opt_in_and_never_written(service, monkeypatch):
    import report_md
    import report_pdf

    def forbidden(*args, **kwargs):
        raise AssertionError('No file exports allowed')

    monkeypatch.setattr(report_md, 'write_report_md', forbidden)
    monkeypatch.setattr(report_pdf, 'write_report_pdf', forbidden)
    async with Client(create_server(service, TOKEN)) as client:
        result = await client.call_tool('get_report', {
            'student': 'anna', 'lesson_date': '2020-01-02',
            'response_format': 'markdown'})
        text = result.content[0].text
        assert '# 📋 Αναφορά — Άννα' in text
        assert '2020' in text and 'page 7' in text
        assert 'https://erp.maliaras.gr/eclass/lesson/10' in text
        assert 'hidden' not in text and 'future' not in text
        assert len(FakeERP.instances) == 1
        with pytest.raises(ToolError):
            await client.call_tool('get_report', {
                'student': 'anna', 'response_format': 'pdf'})
        assert len(FakeERP.instances) == 1


async def test_sanitized_failure_no_retry():
    class Broken:
        calls = 0

        def fetch(self, *args):
            self.calls += 1
            raise RuntimeError('SECRET upstream body')

    broken = Broken()
    async with Client(create_server(broken, TOKEN)) as client:
        with pytest.raises(ToolError) as error:
            await client.call_tool('get_report', {'student': 'anna'})
        assert 'SECRET' not in str(error.value)
        assert 'Stop' in str(error.value)
    assert broken.calls == 1


async def test_auth_and_health(service, monkeypatch):
    monkeypatch.delenv('MALIARAS_MCP_TOKEN', raising=False)
    with pytest.raises(ValueError):
        create_server(service)
    auth = ProxyTokenVerifier(TOKEN)
    assert await auth.verify_token('wrong') is None
    assert (await auth.verify_token(TOKEN)).client_id == 'parent-proxy'
    app = create_server(service, TOKEN).http_app(stateless_http=True)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            assert (await client.get('/healthz')).text == 'ok'
            for headers in ({}, {'Authorization': 'Bearer wrong'}):
                assert (await client.post('/mcp', headers=headers)).status_code == 401
            response = await client.post('/mcp', headers={
                'Authorization': f'Bearer {TOKEN}',
                'Accept': 'application/json, text/event-stream'}, json={
                    'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                    'params': {'protocolVersion': '2025-03-26', 'capabilities': {},
                               'clientInfo': {'name': 'test', 'version': '1'}}})
            assert response.status_code == 200
    assert not FakeERP.instances
