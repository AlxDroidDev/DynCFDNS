# Install test dependencies
pip install -r test_requirements.txt

# Run tests with coverage
coverage run -m unittest test_cfupdater.py
coverage report -m

# Or using pytest
pytest test_cfupdater.py --cov=cfupdater --cov-report=html --cov-report=term-missing