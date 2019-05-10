# LSST Data Management System
# Copyright 2018 AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <http://www.lsstcorp.org/LegalNotices/>.

"""
Code for Verification Elements Baseline documents
"""

import requests
import sys

from marshmallow import Schema, fields, post_load, pre_load

from .config import Config
from .formatters import as_anchor, alphanum_key
from .utils import owner_for_id, as_arrow, HtmlPandocField, \
    MarkdownableHtmlPandocField, test_case_for_key, get_folders

class VerificationElementIssue(Schema):
    key = fields.String(required=True)
    summary = MarkdownableHtmlPandocField()
    status = fields.String()
    description = MarkdownableHtmlPandocField()
    #description = HtmlPandocField()
    components = fields.List(fields.String())
    jira_url = fields.String()
    assignee = fields.Function(deserialize=lambda obj: owner_for_id(obj))
    assignee_id = fields.String(load_from="assignee", required=True)
    requirement_id = fields.String()

    # FIXME: Some of the following seem to be in Jira Markdown and not HTML
    #requirement_verification_siblings = MarkdownableHtmlPandocField()
    #requirement_text = MarkdownableHtmlPandocField()
    #requirement_discussion = MarkdownableHtmlPandocField()
    #higher_level_requirement = fields.String()  # See Below in extract_fields
    parent_requirements = fields.Dict()
    verification_method = fields.String()
    verification_level = fields.String()
    percentage_passing = fields.Float()
    success_criteria = MarkdownableHtmlPandocField()

    @pre_load(pass_many=False)
    def extract_fields(self, data):
        data_fields = data["fields"]
        data["summary"] = data_fields["summary"]
        data["description"] = data_fields["description"]
        data["components"] = [component["name"] for component in data_fields["components"]]
        data["jira_url"] = Config.ISSUE_UI_URL.format(issue=data["key"])
        data["requirement_id"] = data_fields["customfield_13511"]
        #data["requirement_verification_siblings"] = data_fields["customfield_14810"]
        #data["requirement_text"] = data_fields["customfield_13513"]
        #data["requirement_discussion"] = data_fields["customfield_13510"]
        #data["percentage_passing"] = data_fields["customfield_13002"]
        data["success_criteria"] = data_fields["customfield_12204"]

        # Simplify this so we elverage existing owner_for_id code
        data["assignee"] = data_fields["assignee"]["key"]

        # This one may need a regex, it seems to be in jira markdown
        #data["higher_level_requirement"] = data_fields["customfield_13515"]
        data["parent_requirements"] = {}
        if data_fields['customfield_13515']:
            parents=data_fields["customfield_13515"].split(', [')
            for p in parents:
                ps = p.split('|')
                pkey = ps[0].strip('[')
                ps1 = p.split(':')
                psum = ps1[2].strip(']')
                #print (pkey, psum)
                data["parent_requirements"][pkey] = psum

        # The following are not simple objects, but we just want the value
        data["verification_method"] = data_fields["customfield_12002"]["value"]
        if data_fields["customfield_12206"]  == None:
            data["verification_level"] = "NO Verification Level Provided!"
        else:
            data["verification_level"] = data_fields["customfield_12206"]["value"]
        data["status"] = data_fields["status"]["name"]
        return data



#
# Get the list of VEs related to a Sub-Component
#
def get_subcomponents_ves(subcomp):
    rs = requests.Session()
    rs.auth = Config.AUTH
    ves = []
    mr = 100
    response = rs.get(f"https://jira.lsstcorp.org/rest/api/2/search?jql=cf[15001]='{subcomp}'&fields=key&maxResults=0")
    responsej = response.json()
    sa = 0
    total = responsej['total']
    iv = 0
    while total > sa:
        response = rs.get(f"https://jira.lsstcorp.org/rest/api/2/search?jql=cf[15001]='{subcomp}'&fields=key&maxResults={mr}&startAt={sa}")
        responsej = response.json()
        sa = sa + mr
        for i in responsej['issues']:
            iv = iv + 1
            ves.append(i['key'])
            #print(iv, i['key'])
    #if total != iv:
    #    print(f"Verification elements mismatch: found {iv} VEs, expected {total}.")
    #else:
    #    print(f"Found {total} verification elements.")
    return(ves)

#
# Get the VE details
#
def build_ve_model(vetrace):
    v = 0
    verificationelements = {}
    rs = requests.Session()
    rs.auth = Config.AUTH
    for ve in vetrace:
        v = v + 1
        #print(v, ve, Config.ISSUE_URL.format(issue=ve))
        veresp = rs.get(Config.ISSUE_URL.format(issue=ve))
        verespj = veresp.json()
        verificationelement, errors = VerificationElementIssue().load(verespj)
        #print(verificationelement['components'])
        #verificationelements.append(verificationelement)
        #if ve == "LVV-1579":
        #    print(verificationelement)
        #if 'parent_requirements' in verificationelement.keys():
        #    print(ve, verificationelement['parent_requirements'])
        verificationelements[ verificationelement['key'] ] = verificationelement
    return(verificationelements)
