.. _githubaction:

Github Action
=============

SQRBOT-JR will add a github action to the test report repo when it is created. 
This is a manual action and will pull the contents of the LVV from Jira regenerate
the document and push it to lsst.io. 
It will check the update into the branch you call the action on.

If you have permissions on the github repo when you click on the action ``docgen from Jira``
you should see a ``Run workflow`` button appear. 

If the button does not appear you need to be add to the organization to which the repo belongs.
You may find `owners` of the org, who can do this, by selecting `role` `owner` in the pull down on
the right of the org people page e.g. :

-   `DM owners <https://github.com/orgs/lsst-dm/people?query=role%3Aowner>`__
-   `SITCOM owners <https://github.com/orgs/lsst-sitcom/people?query=role%3Aowner>`__
    

To look at an example see `SCTR-14 action <https://github.com/lsst-sitcom/SCTR-14/actions/workflows/docgen_from_Jira.yaml>`__.

Know Problem
------------
Jira occasionally requires a CAPTCHA for the login which is very in convenient. 
This manifests itself by the action failing with a ``403 error``.
The only way around this is to log into Jira from a browser with the user ``lvv-atm-ci-rest`` and answer the CAPTCHA.
The password for this user is in `1password` DM Architecture folder. If you do not have access to this
ask someone in DM Architecture or IT to do it for you.
