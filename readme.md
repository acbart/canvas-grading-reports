# manage-canvas
A set of command line utilities for controlling canvas courses.

Be careful using these, as some can damage the course.

# Create Settings

> python build_ta_report.py

The first time the script is run, a new `settings.yaml` file is created. You will need to add three things to the file:

* First, obtain an API key for Canvas. Set it to the `defaults` -> `canvas-token` keys. https://community.canvaslms.com/docs/DOC-10806-4214724194
* Next, create a new `course` (e.g., `f17_python`) and set the `id` field to the course ID and the `ta_map` field to the relative path to the TA Map YAML file for the course.
* Finally, set the `defaults` -> `course` value to the course you just created.

# TA Report

To generate a new report, simply run the script from the command line. An HTML and PDF file will be generated in the `reports/` folder. You might need to create that folder if it does not exist.

> python build_ta_report.py

You can also optionally specify a specific course label.

> python build_ta_report.py f17_python