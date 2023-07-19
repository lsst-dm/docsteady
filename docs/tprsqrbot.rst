.. _tprsqrbot:

####################################
New test plan report with SQRBOT-JR
####################################

By far the simplest way to get your Test Plan Report is to use SQRBOT-JR.
To do so you need two pieces of information:
- A document Handle (e.g. SCTR-14)
- The test plan id (e.g. LVV-P63)

In addition before extracting a test plan and report using docsteady,
the corresponding document handle has to be added in the ``Document ID`` field in the Jira test plan object.

.. _doc_handle:

Document Handle
---------------
All test report handles are allocated by docushare.
There is no API for docushare so you have to log in and create the appropriate
placeholder document to get the handle.
If you do not have privileges to create a document in docushare ask Rob McKercher.


.. _sqrbot_jr:

SQRBOT-JR
----------

In SLACK start a chat with @sqrbot-jr. Type::

   @sqrbot-jr create project

select ``test-report``, it will ask more questions like the :ref:`handle <doc_handle>` and LVV.
Then sit back, it will create the repo put a document shell in there for you.
It will also add the ``docgen from Jira`` github action to pull contents from
jira when you need it. Look at the actions in the new repo.

Regenerate the document
-----------------------
Once created you may update the document from Jira at anytime using the :ref:`githubaction`.
