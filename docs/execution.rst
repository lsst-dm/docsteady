.. _execution:

#########
Execution
#########

Credentials are needed by `docsteady` to log into JIRA and ZEPHYR.
The easiest way to do this is by setting up the following environment variables::

  export JIRA_USER=<jira-username>
  export JIRA_PASSWORD=<password>
  export ZEPHYR_TOKEN=<token>

Alternatively you may specify them on the command line using the ``--username``, ``--password`` and ``--token'' options.

If none of these are done you will be prompted interactively for each of secrets.

Personal Jira credentials may no longer be used.

For JIRA the JIRA_PASSWORD should be an API token or you may lock out the account.
You can make a token by going to you 'atlassian account security page <https://id.atlassian.com/manage-profile/security>'_
and selecting "Create and Manage API tokens".
You still use your username but use the generated TOKEN instead of your regular password.

For Zephyr there is no choice but API token.
You may generate a token within Jira Cloud by clicking on your account avatar (top right) and
select 'Zephyr scale API access tokens <https://rubinobs.atlassian.net/plugins/servlet/ac/com.kanoah.test-manager/api-access-tokens>`_

For CI purposes, a general set of credentials are available, as specified in section :ref:`auth`.

In order to execute any of the docsteady commands described in the following subsections, a conda environment providing docsteady must be activated, as described in :ref:`install`.

Use ``--help`` to get the list of available options for each of the docsteady commands.

.. _quick:

Quick guide
############

- ``generate-spec``: to generate a Test Specification (baselining test cases)
- ``generate-report``: for test plans and reports
- ``generate-vcd``: to generate the Verification Control Documents
- ``baseline-ve``: to generate Verification Elements baseline documents.

More details on the procedures and logic applied in the document generation
is available in this SPIE Paper :dmtn:`140`.



Test Specification Generation
#############################

Test specifications are extracted using the Jira REST API.
All tests cases included in a TM4J folder, including subfolders, are rendered in the same extraction.
The folder organization in Jira should correspond to the major subsystem components and the MagicDraw model.

The syntax to extract a test specification is the following::

  docsteady generate-spec "</tm4j_folder>" jira_docugen.tex

where ``</tm4j_folder>`` should be replaced by the exact folder where the test cases are defined in the Jira ``Test Cases`` tab.
For example, the command to extract the DM Acceptance test specification, LDM-639, is the following:

``docsteady generate-spec "/Data Management/Acceptance|LDM-639" [jira_docugen.tex]``

Note that:
- the output file `jira_docugen.tex` is optional in the execution of docsteady but required in this context in order to include the extracted information in a \LaTeX~document (i.e. LDM-639.tex). If omitted, the docsteady output will just be printed in the terminal;
- the folder name in Jira includes at the end the test specification document handle. This is a best practice to use when organizing test cases in Jira since it helps to orient the user in the folder structure;
- an appendix with the traceability to the requirements is produced in the file `jira_docugen.appendix.tex`, to be included in the test specification TeX file.


See LDM-639 Git repository as an example.


.. _tprg:

Test Plan and Report Generation
###############################

This is automated - see :ref:`Test plan report with SQRBOT-JR<tprsqrbot>`.

``Important``: before extracting a test plan and report using docsteady,
the corresponding document handle has to be added in the ``Document ID`` field in the Jira test plan object.
This ensures that the Verification Control Document will include this information.

The following command extracts a Test Plan and Report using Jira REST API:

``docsteady generate-tpr <LVV-PXX> <file.tex> [--trace true]``

Where:

- ``LVV-PXX`` is the TM4J object that describes the test campaign, for example ``LVV-P72``;
- ``file.tex`` is the Test Plan and Report tex file where the document will be rendered, for example ``DMTR-231.tex``;
- ``--trace true`` (optional) generates an appendix with the traceability information.

Each TM4J test plan and related information in Jira is rendered in a different Test Plan and Report document,
the filename of which usually corresponds also to the document handle in DocuShare.

The generated file can be built directly into the corresponding pdf, however additional files are required:

- Makefile
- appendix.tex
- history\_and\_info.tex

When creating the Git repository using ``sqrbot-jr``, all the required files should already be present.
For more info on documents, change control and ``sqrbot-jr`` see
`The dev guide <https://developer.lsst.io/project-docs/change-controlled-docs.html#ccd-create>`_.

In case you want to generate a Test Plan and Report for a different subsystem, not DM, you can use the namespace global option::

 docsteady --namespace <NS> generate-tpr <LVV-PXX> <file.tex> [--trace true]

Valid namespaces are:

- SE: system Engineering
- DM: Data Management
- T&S: Telescope & Site

See SCTR-14 or DMTR-231 Git repositories as an example.



Verification Element Baseline Generation
########################################

Verification Elements (VE) are Jira issues in the LVV Jira project, of type ``Verification``.
They are categorized into Components (DM, SITCOM, etc) and Sub-Components.

A VE baseline document is extracted using REST API.
All VE associated with a Jira Component or Sub-Component, if specified, are rendered in the same extraction.

The syntax to extract a VE baseline information is the following::

  ``docsteady [--namespace <CMP>] baseline-ve [--subcomponent <SUBC>] jira\_docugen.tex [--details true]``

The information is saved in the specified ``jira_docugen.tex`` file.
This file has to be included in a \LaTeX~document, where the corresponding context about the Component and Sub-Component is provided.

The ``--namespace <CMP>`` option identifies the Jira component from which to extract the information.
The parameter ``CMP`` shall correspond to the Rubin Observatory sub-systems.
See :ref:`components<components>` for the complete list of components.
If omitted, the DM component is selected by default.

The ``--subcomponent <SUBC>`` is optional. If omitted all verification elements of the specified component will be extracted.
See :ref:`subcomp` for the description of the DM subcomponents.

If the option ``--details true`` is provided, an extra technical note is generated, including all test case details.

Since version 3 a new ``--dump=True'' option is avialalbe.
If this option is added the information extracted from Jira is stored in a json file before the template is used to render it.
This is very useful if you are working with the template and do not need to refresh the information, the extraction can be long.

See LDM-732 Git repository as an example.


.. _subcomp:

Sub-Components
##############

Ideally, Sub-Components  match  the major products of a Rubin subsystem.
They should also be mapped to the product tree defined in the MagicDraw model.

In DM, trying to find a good balance between details and practice, the following components have been defined, in agreement with the DM scientist leader:

- Science
- Service
- Network
- Infrastructure

For each of these subcomponents, a different VE baseline document is extracted.



Verification Control Document Generation
#########################################

The extraction of the Verification Control Document is done using the same APIs described above.
It is very similar to Verification Baseline.

The following command extracts all VCD information regarding ``DM`` and generates the file ``jira_docugen.tex``::

  docsteady [--namespace <COM>] generate-vcd --sql True jira_docugen.tex

When no ``--namespace if provided``, the DM component is selected by default.
The generated file ``jira_docugen.tex`` is meant to be included in LDM-692.tex.

In case you want to generate the VCD for a different LSST/Rubin Observatory subsystem,
just use the corresponding subsystem code configured in the Jira ``component`` field.
See next subsection :ref:`components<components>` for the complete list.

Since version 3 a new ``--dump=True'' option is avialalbe.
If this option is added the information extracted from Jira is stored in a json file before the template is used to render it.
This is very useful if you are working with the template and do not need to refresh the information, the extraction can be long.

The only example of this is LDM-692.

.. _components:

Components - Sub-systems
########################

Follows the list of components configured for the Jira LVV project.
Each component corresponds to a Rubin Observatory Construction subsystem.

- ``CAM``: Camera
- ``DM``: Data Management, the default component for all docsteady commands.
- ``EPO``: Education and Public Outreach
- ``OCS``: Observatory Control System
- ``PSE``: Project System Engineering, used for Commissioning (SitCom)
- ``T&S``: Telescope and Site

In case the subcomponent specified is "None", all VE without subcomponents will be extracted.

