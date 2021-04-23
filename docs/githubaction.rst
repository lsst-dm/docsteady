.. _githubaction:

#############
Github Action
#############

SQRBOT-JR will add a github action to the test report repo when it is created. 
This is a manual action and will pull the contents of the LVV from Jira regenerate
the document and push it to lsst.io. 
It will check the update into the branch you call the action on.

If you have permissions on the github repo when you click on the action ``docgen from Jira``
you should see a ``Run workflow`` button appear. 

To look at an example see `SCTR-14 action <https://github.com/lsst-sitcom/SCTR-14/actions/workflows/docgen_from_Jira.yaml>`.
