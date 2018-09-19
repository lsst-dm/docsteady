docsteady
=========

docsteady is a python package (and optionally Docker container) that talks to 
Jira and the Adaptavist Test Management system to output Test folders and
Test plans to a variety of documents by utilizing pandoc.

# Usage
The defaults of docsteady are to build documents based on DM defaults. There
are two commands you can give to docsteady to do this, `generate-spec` and
`generate-cycle`.

## Docker quickstart
```shell
# Use appropriate credentials
docker run -it --rm \
    -v `pwd`:/workspace -w /workspace lsstdm/docsteady:latest \
    docsteady generate-spec "/Data Management/Prompt" jira_docugen.tex
```

## CLI

See the [generated documentation](https://lsst-dm.github.io/docsteady).

# Writing Templates

The templating engine we use is jinja2. (See http://jinja.pocoo.org/docs/2.10/).
We use pandoc for converting things between different formats.

In general, you can write a a template using jinja in any language supported
by pandoc, including latex, html, markdown, and restructured text. Our
default language is latex. 


## Resolving templates

For both goals, **docsteady will first look for a template in
`load-from`, which defaults to the current working directory**,
and if no template is found, **it will then default to the templates
defined in this package under  `docsteady/templates`**.

* In the case of the `generate-spec` goal, it will by default look for a
`spec` template.

* In the case of `generate-cycle` goal, it will look for a `cycle` template.

* When no options are presented to docsteady, the defaults are:
  * `dm-spec.latex.jinja2` for `generate-spec` 
  * `dm-cycle.latex.jinja2` for `generate-cycle`    
  * The generate format is `{namespace}-{goal}.{template_format}.jinja2`

* An appendix can be processed separately. Accordingly, the defaults are:
  * `dm-spec-appendix.latex.jinja2` for `generate-spec` 
  * `dm-cycle-appendix.latex.jinja2` for `generate-cycle`
  * The general format is `{namespace}-{goal}-appendix.{template_format}.jinja2`


## Fields
### String, Integer, etc...
This is just simple types and are treated as such in the templates.

### Timestamps (arrow)
Timestamps are parsed and loaded to arrow objects. This allows flexible formatting
when writing out to template. Timestamps are converted to `US/Pacific` by default.

A naive formatting of an arrow timestamp looks like this:

`{{ testresult.execution_date.format('YYYY-MM-DD HH:mm:ss') }}`

For more information on formatting and conversion, see the arrow documentation:
https://arrow.readthedocs.io/en/latest/.

### HtmlPandocField
Fields that are designated as `HtmlPandocField` means that docsteady will take the HTML output
verbatim from Jira and translate that directly to the template language. This is possible
because the Adaptavist Test Management framework provides a rich text editor, and stores
the output as HTML. For Latex templates, this means your HTML is close to WYSIWYG in
Latex.

### MarkdownableHtmlPandocField
Fields that are designated as `MarkdownableHtmlPandocField` will be intepreted primarily
as an `HtmlPandocField` _unless_ a special tag is found in the first line of the
field:

`[markdown]: #`

If that tag is found, the text in jira field is interpreted as plain text, (ignoring any
HTML formatting) and translated to the target template language. This includes code
highlighting.

A more complete example:

~~~markdown
[markdown]: #

# This is a markdown version of a test step

We can embed code in it:
```python
import sys
sys.exit(1)
```
... And it will be formatted in the final document just fine.
~~~


## Models
There are currently two main types of documents that can be generated - test specs and test cycles.
In both cases, there are models in the respective files (`docsteady/spec.py`, `docsteady/cycle.py`)
and a small amount of code to aid in building the models.

## Spec model and `generate-spec` target

### `generate-spec` objects

* `testcases`: List of testcases (ordered) (type: `List[TestCase]`)
* `requirements_to_testcases`: Map of requirement key to testcase key 
(type: `Dict[str, str]`)
* `requirements_map`: All found requirements - requirement key to requirement 
(type: `Dict[str, Issue]`)
* `testcases_map`: All found testcases - testcase key to testcase 
(type: `Dict[str, TestCase]`). This includes all test cases found in test scripts.


### Spec Model
The following is a simplified version of the code in `docsteady/spec.py` to aid
template development.

```python
class TestCase(Schema):
    key = fields.String(required=True)
    name = fields.String(required=True)
    #: String of owner's fullname
    owner = fields.Function(deserialize=lambda obj: owner_for_id(obj))
    #: Owner's Jira ID
    owner_id = fields.String(load_from="owner", required=True)
    #: Url of this test case
    jira_url = fields.String()
    component = fields.String()
    #: Nominal type is an arrow Timestamp
    created_on = fields.Function(deserialize=lambda o: as_arrow(o['createdOn'])) 
    precondition = HtmlPandocField()
    objective = HtmlPandocField()
    version = fields.Integer(load_from='majorVersion', required=True)
    status = fields.String(required=True)
    priority = fields.String(required=True)
    labels = fields.List(fields.String(), missing=list())
    #: Nominal type is a List[TestStep], see below
    test_script = fields.Method(deserialize="process_steps", load_from="testScript", required=True)
    issue_links = fields.List(fields.String(), load_from="issueLinks")

    # Just in case it's necessary - these aren't guaranteed to be correct
    custom_fields = fields.Dict(load_from="customFields")

    # custom fields go here and in pre_load
    verification_type = fields.String()
    verification_configuration = HtmlPandocField()
    predecessors = HtmlPandocField()
    critical_event = fields.String()
    associated_risks = HtmlPandocField()
    unit_under_test = HtmlPandocField()
    required_software = HtmlPandocField()
    test_equipment = HtmlPandocField()
    test_personnel = HtmlPandocField()
    safety_hazards = HtmlPandocField()
    required_ppe = HtmlPandocField()
    postcondition = HtmlPandocField()

    # synthesized fields (See @pre_load and @post_load)
    doc_href = fields.String()

    #: See below
    requirements = fields.Nested(Issue, many=True)

class Issue(Schema):
    key = fields.String(required=True)
    summary = fields.String()
    jira_url = fields.String()

class TestStep(Schema):
    index = fields.Integer()
    test_case_key = fields.String(load_from="testCaseKey")
    description = MarkdownableHtmlPandocField()
    expected_result = MarkdownableHtmlPandocField(load_from="expectedResult")
    test_data = MarkdownableHtmlPandocField(load_from="testData")
```

### Simple Example
If you added example template (`docsteady/templates/example-spec.markdown.jinja2`),
defined as:

```jinja2
# Testcases

{% for testcase in testcases %}
## {{ testcase.name }}
On the web at {{ testcase.jira_url }}

### Requirements:
{% for requirement in testcase.requirements %}
* {{ requirement.key }} at {{ requirement.jira_url }}
{% endfor %}

{% endfor %}
```

You could generate the resultant file, in latex (by default) via:
* `docsteady --namespace example --template markdown generate-spec "/Data Management/Prompt`

Or actually ask for it in markdown:
* `docsteady --namespace example --template markdown generate-spec --format markdown "/Data Management/Prompt"`

Or HTML:
* `docsteady --namespace example --template markdown generate-spec --format html "/Data Management/Prompt"`

## Cycle model and `generate-cycle` 

### `generate-cycle` template objects
* `testcycle`: Test Cycle object (type: `TestCycle`)
* `testresult`: List of Test results as found from the test cycle (type: `List[TestResult]`)
* `testcases_map`: All found testcases when processing test results - testcase key to testcase 
(type: `Dict[str, TestCase]`). This includes all test cases found from the test results.

### Cycle model

```python
class TestCycle(Schema):
    key = fields.String(required=True)
    name = fields.String(required=True)
    description = fields.String(required=True)
    status = fields.String(required=True)
    execution_time = fields.Integer(required=True, load_from="executionTime")
    created_on = fields.Function(deserialize=lambda o: as_arrow(o['createdOn']))
    updated_on = fields.Function(deserialize=lambda o: as_arrow(o['updatedOn']))
    planned_start_date = fields.Function(deserialize=lambda o: as_arrow(o['plannedStartDate']))
    owner_id = fields.String(load_from="owner", required=True)
    owner = fields.Function(deserialize=lambda obj: owner_for_id(obj))
    created_by = fields.Function(deserialize=lambda obj: owner_for_id(obj), load_from="createdBy")
    custom_fields = fields.Dict(load_from="customFields")
    items = fields.Nested(TestCycleItem, many=True)

    # custom fields
    software_version = HtmlPandocField()

class TestCycleItem(Schema):
    id = fields.Integer(required=True)
    test_case_key = fields.Function(deserialize=lambda key: test_case_for_key(key)["key"],
                                    load_from='testCaseKey', required=True)
    user_id = fields.String(load_from="userKey")
    user = fields.Function(deserialize=lambda obj: owner_for_id(obj["userKey"]))
    execution_date = fields.Function(deserialize=lambda o: as_arrow(o['executionDate']))
    status = fields.String(required=True)

class TestResult(Schema):
    id = fields.Integer(required=True)
    key = fields.String(required=True)
    automated = fields.Boolean(required=True)
    environment = fields.String()
    execution_time = fields.Integer(load_from='executionTime', required=True)
    test_case_key = fields.Function(deserialize=lambda key: test_case_for_key(key)["key"],
                                    load_from='testCaseKey', required=True)
    execution_date = fields.Function(deserialize=lambda o: as_arrow(o), required=True,
                                     load_from='executionDate')
    script_results = fields.Nested(ScriptResult, many=True, load_from="scriptResults",
                                   required=True)
    issues = fields.Nested(Issue, many=True)
    issue_links = fields.List(fields.String(), load_from="issueLinks")
    user_id = fields.String(load_from="userKey")
    user = fields.Function(deserialize=lambda obj: owner_for_id(obj), load_from="userKey")
    status = fields.String(load_from='status', required=True)

class ScriptResult(Schema):
    index = fields.Integer(load_from='index')
    expected_result = MarkdownableHtmlPandocField(load_from='expectedResult')
    execution_date = fields.String(load_from='executionDate')
    description = MarkdownableHtmlPandocField(load_from='description')
    comment = MarkdownableHtmlPandocField(load_from='comment')
    status = fields.String(load_from='status')
```