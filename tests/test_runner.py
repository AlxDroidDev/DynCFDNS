import unittest
import coverage

if __name__ == '__main__':
    # Start coverage
    cov = coverage.Coverage()
    cov.start()

    # Discover and run tests
    loader = unittest.TestLoader()
    suite = loader.discover('.', pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Stop coverage and generate report
    cov.stop()
    cov.save()

    print("\nCoverage Report:")
    cov.report(show_missing=True)

    # Generate HTML report
    cov.html_report(directory='htmlcov')
    print("\nHTML coverage report generated in 'htmlcov' directory")