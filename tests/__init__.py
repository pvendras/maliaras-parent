import os

# Test-only children; real ones come from the parent's .env.
os.environ.setdefault('MALIARAS_STUDENTS', 'anna:Άννα,nikos:Νίκος')
