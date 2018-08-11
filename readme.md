# manage-canvas
A set of command line utilities for controlling canvas courses.

Be careful using these, as some can damage the course.

# Requirements

Make sure you pip install the requirements.txt file!

# Create Settings

> python build_ta_report.py

OR

> python edit_dates.py

The first time one of the scripts is run, a new `settings.yaml` file is created. You will need to add three things to the file:

* First, obtain an API key for Canvas. Set it to the `defaults` -> `canvas-token` keys. https://community.canvaslms.com/docs/DOC-10806-4214724194
* Next, create a new `course` (e.g., `f17_python`) and set the `id` field to the course ID and the `ta_map` field to the relative path to the TA Map YAML file for the course.
* Finally, set the `defaults` -> `course` value to the course you just created.

# TA Report

To generate a new report, simply run the script from the command line. An HTML and PDF file will be generated in the `reports/` folder. You might need to create that folder if it does not exist.

> python build_ta_report.py

You can also optionally specify a specific course label.

> python build_ta_report.py f17_python

# Edit Dates

> python edit_dates.py -h

Currently, only the `import` and `export` commands work. 

The format for the date strings should be:

> MM/DD/YY HH:MMpm

For example

> 8/11/18 1:00m

Because of time zones, life can be difficult. I've never quite figured out if I got DST correct either.