# Exam registration

The program notifies you periodically if there is an open sign up for an exam specified by the user.

To run the program you simply need to run one of the included batch files, which have the following function:
  - The run.cmd runs the program checking only for first time exam registration, be wary of courses with more than one exam!
  - The runAddCourses.cmd allows you to add courses prior to executing everything like the run.cmd would.
  - The runCheckResits.cmd checks all courses for exams regardless of whether the user had already signed up for them or not, useful for courses with multiple exams!

To have it working properly a creds.py file is required. A credsTemplate.py is provided but the request URLs have been left out on purpose.
These URLs are necessary to run the program so if you really want to make use of this contact me or figure the URLs out yourself.
Lastly, the user should have installed the python libraries provided in the requirements.txt.
  
It is recommended to have either the run.cmd or runCheckResists.cmd running on a schedule with a random time offset, using windows scheduler for example.
