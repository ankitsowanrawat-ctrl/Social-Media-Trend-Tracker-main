import os
import sys

# Ensure root directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import and run the dashboard app
from dashboard.app import TrendTrackerDashboard

if __name__ == "__main__":
    dashboard = TrendTrackerDashboard()
    dashboard.run()
