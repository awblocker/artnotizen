"""Setup for artnotizen
"""
import ez_setup
ez_setup.use_setuptools()
import os
from setuptools import setup

setup(name="artnotizen",
      version="0.1",
      url="https://github.com/awblocker/artnotizen/",
      description="Markdown-based note organization",
      author="Alexander W Blocker",
      author_email="ablocker@gmail.com",
      license="Apache v2.0",
      install_requires=["jinja2>=2.7"],
      # Keeping all Python code for package in lib directory
      package_dir={"artnotizen": "src"},
      packages=["artnotizen"],
      package_data={"artnotizen": ["templates/*"]},
      scripts=[os.path.join("scripts/", f) for f in os.listdir("scripts/")],
     )
