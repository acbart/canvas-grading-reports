# manage-canvas

A set of command line utilities for controlling canvas courses.

# Requirements

Make sure you pip install the requirements.txt file

> pip install -r requirements.txt

This is for Python 3.

# Create Settings

> python build_ta_report.py

OR

> python edit_dates.py

The first time one of the scripts is run, a new `settings.yaml` file is created. You will need to add three things to the file:

* First, [obtain an API key for Canvas](https://community.canvaslms.com/docs/DOC-10806-4214724194). Set it to the `defaults` -> `canvas-token` keys.
* You'll need to make sure the `defaults` -> `canvas-url` is set to the proper API URL for your university (e.g., `"https://udel.instructure.com/api/v1/"`)
* You'll need to make sure the `defaults` -> `canvas-base-url` is set to the proper Canvas URL for your university (e.g., `"https://udel.instructure.com/"`)
* Next, create a new `course` (e.g., `f17_python`) and set the `id` field to the course ID and the `ta_map` field to the relative path to the TA Map YAML file for the course. It's okay if you leave a blank string for the `ta_map`, but make sure you provide the `id`! You can find it in the URL when you visit the course page on the Canvas site.
* Finally, set the `defaults` -> `course` value to the course you just created.

```
defaults:
    canvas-token: "SECRET_KEY"
    canvas-url: "https://udel.instructure.com/api/v1/"
    canvas-base-url: "https://udel.instructure.com/"
    course: f18_cisc108
courses:
    f18_cisc108:
        id: 1421509
        ta_map: "tas/f18_cisc108_ta_map.yaml"
```

# Edit Dates

> python edit_dates.py -h

Currently, only the `import` and `export` commands work. 

The format for the date strings should be:

> MM/DD/YY HH:MMpm

For example

> 8/11/18 1:00m

Because of time zones, life can be difficult. I've never quite figured out if I got DST correct either.

# TA Report

To generate a new report, run the script from the command line. An HTML and PDF file will be generated in the `reports/` folder. You might need to create that folder if it does not exist.

> python build_ta_report.py

You can also optionally specify a specific course label.

> python build_ta_report.py f17_python

I'll be honest, this is a pretty fragile script, given its complexity.

If you want to associate TAs with specific groups, you'll need to provide the mapping in the yaml file:

```yaml
Group Name 1: TA A Display Name
Group Name 2: TA B Display Name
Group Name 3: TA C Display Name
```

The group name must match exactly with the group on Canvas, but the TA display name can be whatever you want. Group names must be unique, but the same TA might have multiple groups.
