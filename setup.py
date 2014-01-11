"""Setup for artnotizen
"""
import os
from distutils.core import setup

setup(name="artnotizen",
      version="0.1",
      url="http://www.awblocker.com",
      description="Markdown-based note organization",
      author="Alexander W Blocker",
      author_email="ablocker@gmail.com",
      # Keeping all Python code for package in lib directory
      package_dir={"artnotizen": "src"},
      packages=["artnotizen"],
      package_data={"artnotizen": ["templates/*"]},
      scripts=[os.path.join("scripts/", f) for f in os.listdir("scripts/")],
     )
