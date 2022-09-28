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
Code for VCD
"""

import pymysql
import requests
import os
from marshmallow import Schema, fields, pre_load
from collections import Counter

from .config import Config
from .utils import get_tspec, HtmlPandocField


class VerificationE(Schema):
    key = fields.String(required=True)
    summary = fields.String()
    jira_url = fields.String()
    assignee = fields.String()
    description = HtmlPandocField()
    ve_status = fields.String()
    ve_priority = fields.String()
    req_id = fields.String()
    req_spec = HtmlPandocField()
    req_discussion = HtmlPandocField()
    req_priority = fields.String()
    req_doc_id = fields.String()
    req_params = HtmlPandocField()
    raw_upper_req = HtmlPandocField()
    upper_reqs = fields.List(fields.String(), missing=list())
    raw_test_cases = HtmlPandocField()
    test_cases = fields.List(fields.String(), missing=list())
    verified_by = fields.Dict(fields.Dict(), missing=list())

    @pre_load(pass_many=False)
    def extract_fields(self, data):
        data_fields = data["fields"]
        data["summary"] = data_fields["summary"]
        data["jira_url"] = Config.ISSUE_UI_URL.format(issue=data["key"])
        if data_fields["assignee"]:
            data["assignee"] = data_fields["assignee"]["displayName"]
        else:
            data["assignee"] = "UNASSIGNED"
        data["description"] = data['renderedFields']["description"]
        data["ve_status"] = data_fields["status"]["name"]
        if data_fields["priority"]:
            data["ve_priority"] = data_fields["priority"]["name"]
        try:
            data["req_id"] = data_fields["customfield_15502"]
        except KeyError:
            print(f'Failed to get req_id customfield_15502 for {data["key"]}')
        data["req_spec"] = data['renderedFields']["customfield_13513"]
        data["req_discussion"] = data['renderedFields']["customfield_13510"]
        if data_fields["customfield_15204"]:
            data["req_priority"] = data_fields["customfield_15204"]["value"]
        data["req_params"] = data['renderedFields']["customfield_13512"]
        data["raw_upper_req"] = data_fields["customfield_13515"]
        data["raw_test_cases"] = data_fields["customfield_15106"]
        data["verified_by"] = self.extract_verified_by(data_fields)
        ref = data_fields["customfield_14701"]["value"]
        if (":" in ref):
            ref = ref.split(":")[0]
        data["req_doc_id"] = ref
        return data

    def extract_verified_by(self, data_fields):
        if "issuelinks" not in data_fields.keys():
            return {}
        issuelinks = data_fields["issuelinks"]
        verified_by = {}
        for issue in issuelinks:
            if "inwardIssue" in issue.keys():
                if issue["inwardIssue"]["fields"]['issuetype']['name'] == "Verification" \
                        and issue['type']['inward'] == "verified by":
                    tmp_issue = dict()
                    tmp_issue['key'] = issue["inwardIssue"]["key"]
                    tmp_issue['summary'] = issue["inwardIssue"]["fields"]["summary"]
                    verified_by[issue["inwardIssue"]["key"]] = tmp_issue

        return verified_by


class Coverage_Count:
    """Coverage for Requirements and Verification Elements"""
    notcs = 0
    noexectcs = 0
    failedtcs = 0
    passedtcs = 0
    passedtcs_name = "Passed TCs"
    passedtcs_label = "sec:passedtcs"

    def total_count(self):
        return self.notcs + self.noexectcs + self.failedtcs + self.passedtcs


def runstatus(trs):
    if trs == "Pass":
        status = 'passed'
    elif trs == "Pass w/ Deviation":
        status = 'cndpass'
    elif trs == "Fail":
        status = 'failed'
    elif trs == "In Progress":
        status = 'inprog'
    elif trs == "Blocked":
        status = 'blocked'
    else:
        status = 'notexec'
    return status


def build_vcd_model(component):
    # build the vcd. Only Verification Issues are considered.
    # global tcases

    rs = requests.Session()

    # get component id
    resp = rs.get("https://jira.lsstcorp.org/rest/api/2/project/LVV/components",
                  auth=Config.AUTH)
    cmps = resp.json()
    component_id = ''
    for c in cmps:
        if c['name'] == component:
            component_id = c['id']
            break
    if component_id == '':
        print(f'Error. Component {component} not found in LVV project')
        exit()

    # get the number of issue in the componenet
    resp = rs.get("https://jira.lsstcorp.org/rest/api/latest/component/{component_id}/relatedIssueCounts",
                  auth=Config.AUTH)
    cmp_count: {}
    cmp_count = resp.json()
    max_res = cmp_count['issueCount']

    print(f"Getting {max_res} Verification Elements from {component}.")
    resp = rs.get(Config.VE_SEARCH_URL.format(cmpnt=component, maxR=max_res),
                  auth=Config.AUTH)
    resp.raise_for_status()

    velem = {}
    reqs = {}

    veresp = resp.json()
    i = 0
    for ve in veresp['issues']:
        i = i + 1
        tmp = dict()
        tmp['jkey'] = ve['key']
        # tmp['summary'] = ve['fields']['summary']
        ves = ve['fields']['summary'].split(':')
        # tmp['veId'] = ves[0]
        tmp['veSummary'] = ves[1]
        tmp['req'] = ve['fields']['customfield_13511']
        tmp['vmethod'] = ve['fields']['customfield_12002']['value']
        tmp['reqDoc'] = ve['fields']['customfield_13703']
        tmp['reqId'] = ve['fields']['customfield_13511']
        # if 'value' not in ve['fields']['customfield_12206'].keys():
        if not ve['fields']['customfield_12206']:
            # if 'customfield_12206' not in ve['fields'].keys():
            tmp['vlevel'] = 'None'
        else:
            tmp['vlevel'] = ve['fields']['customfield_12206']['value']
        if tmp['reqId'] not in reqs.keys():
            rtmp = dict()
            rtmp['desc'] = ve['fields']['customfield_13513']
            # print(ve['fields']['customfield_13513'])
            rtmp['reqDoc'] = ve['fields']['customfield_13703']
            rtmp['VEs'] = []
            rtmp['VEs'].append(ves[0])
            reqs[tmp['reqId']] = rtmp
        else:
            reqs[tmp['reqId']]['VEs'].append(ves[0])

        # print(i, tmp)
        tcraw = rs.get(Config.ISSUETCASES_URL.format(issuekey=tmp['jkey']),
                       auth=Config.AUTH)
        tcrawj = tcraw.json()
        tmp['tcs'] = {}
        for tc in tcrawj:
            if tc['key'] not in tmp['tcs'].keys():
                tmp['tcs'][tc['key']] = {}
                tmp['tcs'][tc['key']]['tspec'] = get_tspec(tc['folder'])
                if 'lastTestResultStatus' in tc.keys():
                    tmp['tcs'][tc['key']]['lastR'] = tc['lastTestResultStatus']
                else:
                    tmp['tcs'][tc['key']]['lastR'] = None
                if tc['key'] not in Config.CACHED_TESTCASES.keys():
                    tctmp = {}
                    if tc['owner']:
                        tctmp['owner'] = tc['owner']
                    else:
                        tctmp['owner'] = ""
                    tctmp['critical'] = tc['customFields']['Critical Event?']
                    tctmp['vtype'] = tc['customFields']['Verification Type']
                    if 'objective' in tc.keys():
                        tctmp['objective'] = tc['objective']
                    else:
                        tctmp['objective'] = ""
                    tctmp['name'] = tc['name']
                    tctmp['status'] = tc['status']
                    tctmp['folder'] = tc['folder']
                    tctmp['tspec'] = get_tspec(tc['folder'])
                    Config.CACHED_TESTCASES[tc['key']] = tctmp
        velem[ves[0]] = tmp

    print("\nGot", len(velem), "Verification Elements on", len(reqs), "Requirements. Found",
          len(Config.CACHED_TESTCASES), ' related test cases.')

    for tck in Config.CACHED_TESTCASES.keys():
        # print(tck, end="")
        tcd = rs.get(Config.TESTCASERESULT_URL.format(tcid=tck),
                     auth=Config.AUTH)
        if tcd.status_code == 404:
            # print('Error on -------> ', tck)
            # print(Config.TESTCASERESULT_URL.format(tcid=tck))
            continue
        else:
            tcdj = tcd.json()
            tmpr = dict()
            tmpr['status'] = runstatus(tcdj['status'])
            # print('(', tcdj['status'],')', end="")
            tmpr['exdate'] = tcdj['executionDate'][0:10]
            tmpr['tester'] = tcdj['executedBy']
            tmpr['key'] = tcdj['key']
            if 'comment' in tcdj.keys():
                tmpr['comment'] = tcdj['comment']
            else:
                tmpr['comment'] = ""
            # print(Config.TESTPLANCYCLE_URL.format(trk=tcdj['key']))
            tctp = rs.get(Config.TESTPLANCYCLE_URL.format(trk=tcdj['key']),
                          auth=Config.AUTH)
            tctpj = tctp.json()
            if 'testRun' in tctpj.keys():
                tmpr['tcycle'] = tctpj['testRun']['key']
                if 'testPlan' in tctpj['testRun'].keys():
                    tmpr['tplan'] = tctpj['testRun']['testPlan']['key']
                    tpl = rs.get(Config.TPLANCF_URL.format(tpk=tmpr['tplan']))
                    tplj = tpl.json()
                    tmpr['dmtr'] = tplj['customFields']['Document ID']
                else:
                    tmpr['tplan'] = "NA"
                    tmpr['dmtr'] = "NA"
            else:
                tmpr['tcycle'] = "NA"
                tmpr['dmtr'] = "NA"
                tmpr['tplan'] = "NA"
            Config.CACHED_TESTCASES[tck]['lastR'] = tmpr

    fsum = open("summary.tex", 'w')
    print('\\newpage\n\\section{Summary Information}', file=fsum)
    print('\\begin{longtable}{ll}\n\\toprule', file=fsum)
    print(f"Number of Requirements: & {len(reqs)} \\\\", file=fsum)
    print(f"Number of Verification Elements: & {len(velem)} \\\\", file=fsum)
    print(f"Number of Test Cases: & {len(Config.CACHED_TESTCASES)} \\\\", file=fsum)
    print('\\bottomrule\n\\end{longtable}', file=fsum)
    fsum.close()


def db_get(dbquery) -> {}:
    """returns query result in a 2dim matrix"""
    p = Config.DB_PARAMETERS
    db = pymysql.connect(p["host"], p["user"], p['pwd'], p["schema"], read_timeout=1000)
    cursor = db.cursor()
    # try to reconnect in case of lost connection
    #  this seems to happen sometime when connected from far away (Europe)
    db.ping(reconnect=True)
    try:
        cursor.execute(dbquery)
    except BaseException:
        print(dbquery)
        exit
    data = cursor.fetchall()
    db.close()

    res = []

    for row in data:
        # print(row)
        tmp = []
        for col in row:
            # print(str(col)+" ", end='')
            tmp.append(col)
        # print("")
        res.append(tmp)

    return res


def init_jira_status():
    """initialize jst containing the statuses from Jira"""
    global jst
    jst = dict()
    query = "select id, pname from issuestatus"
    rawst = db_get(query)
    for st in rawst:
        jst[st[0]] = st[1]
    print('jira status - ', jst)


def init_priority():
    """initialize jpr containing the priorities from Jira"""
    global jpr
    jpr = dict()
    query = "select id, pname from priority"
    rawst = db_get(query)
    for st in rawst:
        jpr[st[0]] = st[1]
    print('priorities - ', jpr)


def get_tc_results(tc):
    """return last execution result"""
    results = dict()
    query = ("select rs.name as status, plan.key as tplan, run.key as tcycle, "
             "tr.`EXECUTION_DATE`, cfv.`STRING_VALUE` as dmtr from AO_4D28DD_TEST_CASE tc "
             "join AO_4D28DD_TEST_RESULT tr on tc.`ID` = tr.`TEST_CASE_ID` "
             "join AO_4D28DD_TRACE_LINK lnk on tr.`TEST_RUN_ID` = lnk.`TEST_RUN_ID` "
             "join AO_4D28DD_TEST_RUN run on lnk.`TEST_RUN_ID` = run.`ID` "
             "join AO_4D28DD_TEST_SET plan on lnk.`TEST_PLAN_ID` = plan.id "
             "join AO_4D28DD_RESULT_STATUS rs on tr.`TEST_RESULT_STATUS_ID` = rs.id "
             "join AO_4D28DD_CUSTOM_FIELD_VALUE cfv on lnk.`TEST_PLAN_ID` = cfv.`TEST_SET_ID` "
             "where tc.key = '" + tc + "' and cfv.`CUSTOM_FIELD_ID`=66 and tr.`EXECUTION_DATE` is not NULL")
    trdet = db_get(query)
    if len(trdet) != 0:
        results['status'] = runstatus(trdet[0][0])
        results['tplan'] = trdet[0][1]
        results['tcycle'] = trdet[0][2]
        if trdet[0][3]:
            results['exdate'] = trdet[0][3].strftime('%Y-%m-%d')
        else:
            results['exdate'] = None
        results['dmtr'] = trdet[0][4]
    else:
        results = None
    return results


def get_tcs(veid):
    """for a given VE (id) return the related test cases
       and populate in parallel the global tcases """
    # global tcases
    query = ("select tc.key, tc.FOLDER_ID, tc.LAST_TEST_RESULT_STATUS_ID, aos.name "
             "from AO_4D28DD_TEST_CASE tc "
             "inner join AO_4D28DD_TRACE_LINK il on tc.id = il.test_case_id "
             "inner join jiraissue ji on il.issue_id = ji.id "
             "inner join AO_4D28DD_RESULT_STATUS aos on tc.status_id = aos.ID "
             "where tc.archived = 0 and ji.id = " + str(veid))
    rawtc = db_get(query)
    tcs = {}
    for tc in rawtc:
        # print(tc)
        if tc[0] not in tcs:
            if tc[0] in Config.CACHED_TESTCASES.keys():
                tcs[tc[0]] = Config.CACHED_TESTCASES[tc[0]]
            else:
                tcs[tc[0]] = {}
                tcs[tc[0]]['status'] = tc[3]
                tcs[tc[0]]['tspec'] = get_tspec_r(tc[1])
                if tc[2]:
                    tcs[tc[0]]['lastR'] = get_tc_results(tc[0])
                else:
                    tcs[tc[0]]['lastR'] = None
                Config.CACHED_TESTCASES[tc[0]] = tcs[tc[0]]
    return tcs


def get_ves(comp):
    """gets information for all Verification Elementes for a Component
       it returns also the reqs and test cases related to them"""
    global veduplicated
    jst = Config.jst
    jpr = Config.jpr

    velements = dict()
    reqs = dict()
    verifying_ves = []
    # get all VE for the provided component
    query = ("select ji.issuenum, ji.id, ji.summary, ji.issuestatus, ji.priority from jiraissue ji "
             "inner join nodeassociation na ON ji.id = na.source_node_id "
             "inner join component c on na.`SINK_NODE_ID`=c.id "
             " where ji.project = 12800 and ji.issuetype = 10602 and c.cname='" + comp + "'")
    raw_ves = db_get(query)

    v = 0
    for ve in raw_ves:
        print(f"{ve[0]}.", end="", flush=True)
        if ve[3] != '11713':  # ignore DESCOPED VEs
            v = v + 1
            tmpve = dict()
            tmpve['jkey'] = 'LVV-' + str(ve[0])
            ves = ve[2].split(':')
            tmpve['status'] = jst[ve[3]]
            if ve[4]:
                tmpve['priority'] = jpr[ve[4]]
            else:
                tmpve['priority'] = "Not Specified"
            # get VEs that may verify this VE, instead of test cases
            query = ("select ji.issuenum, ji.summary from jiraissue ji "
                     "inner join issuelink il on il.source = ji.id "
                     "where destination = " + str(ve[1]) + " and linktype = 10700 and ji.issuetype = 10602")
            raw_vby = db_get(query)
            if len(raw_vby) > 0:
                vbytmp = []
                for vby in raw_vby:
                    tsum = vby[1].split(':')
                    vbytmp.append(tsum[0])
                    verifying_ves.append(str(vby[0]))
                tmpve['verified_by'] = vbytmp  # was without _ no idea how it worked a year earlier

            # get the parent requirement
            query = ("select cf.id, cf.cfname, cvf.textvalue, "
                     "(select customvalue from customfieldoption where id = cvf.stringvalue) "
                     " from customfieldvalue cvf "
                     "inner join customfield cf on cvf.customfield = cf.id "
                     "inner join jiraissue ji on cvf.issue = ji.id "
                     "where ji.id = " + str(ve[1]) + " and cf.id in (13511, 13703, 15204, 13513)")
            raw_cfs = db_get(query)
            for cf in raw_cfs:
                if cf[2]:
                    tmpve[cf[1]] = cf[2]
                else:
                    tmpve[cf[1]] = cf[3]
                # print(f">{{p}}< {{v}}".format(p=cf[1],v=tmpve[cf[1]]))
            if tmpve['Requirement ID'] not in reqs.keys():
                # print(tmpve['Requirement ID'])
                rtmp = dict()
                if 'Requirement Specification' in tmpve.keys():
                    rtmp['reqDoc'] = tmpve['Requirement Specification']
                else:
                    rtmp['reqDoc'] = ""
                rtmp['reqTitle'] = ves[1].strip()
                if 'Requirement Text' in tmpve.keys():
                    rtmp['reqText'] = tmpve['Requirement Text']
                else:
                    rtmp['reqText'] = ""
                rtmp['VEs'] = []
                rtmp['VEs'].append(ves[0])
                if "Requirement Priority" in tmpve.keys():
                    rtmp['priority'] = tmpve['Requirement Priority']
                else:
                    rtmp['priority'] = "Not Set"
                reqs[tmpve['Requirement ID']] = rtmp
            else:
                if ves[0] not in reqs[tmpve['Requirement ID']]['VEs']:
                    reqs[tmpve['Requirement ID']]['VEs'].append(ves[0])
            tmpve['tcs'] = []
            tmpve['tcs'] = get_tcs(ve[1])
            # print(tmpve['jkey'], tmpve['tcs'])
            if ves[0] in velements.keys():
                print("  Duplicated:", ves[0], tmpve['jkey'])
                print("    existing:", velements[ves[0]]['jkey'])
                veduplicated[tmpve['jkey']] = velements[ves[0]]['jkey']
            else:
                velements[ves[0]] = tmpve
            if v % 1000 == 0:
                print(f"\n[Found {v} VEs. Continuing...]")

    if len(verifying_ves) > 0:
        # get details on VEs verifying some of the component's VEs,
        # but not part of the selected component/subcomponent
        query = "select ji.issuenum, ji.id, ji.summary, ji.issuestatus, ji.priority, c.cname " \
                "from jiraissue ji " \
                "inner join nodeassociation na ON ji.id = na.source_node_id " \
                "inner join component c on na.`SINK_NODE_ID`=c.id " \
                "where ji.project = 12800 and ji.issuetype = 10602 " \
                f"and ji.issuenum in ({', '.join(verifying_ves)})"
        extra_ves = db_get(query)
        for eve in extra_ves:
            eves = eve[2].split(':')
            if eves[0] not in velements.keys():
                print(eve[0], eve[5])
                etmpve = dict()
                etmpve['jkey'] = 'LVV-' + str(eve[0])
                etmpve['status'] = jst[eve[3]]
                if eve[4]:
                    etmpve['priority'] = jpr[eve[4]]
                else:
                    etmpve['priority'] = "Not Specified"
                etmpve['tcs'] = []
                etmpve['tcs'] = get_tcs(eve[1])
                etmpve['cname'] = eve[5]
                velements[eves[0]] = etmpve

    return velements, reqs


def get_tspec_r(fid):
    """recursively browse the folders
    until finding the test spec of the root (NULL)"""
    if not fid:
        return ""
    query = "select name, parent_id from AO_4D28DD_FOLDER where id = " + str(fid)
    # print(query)
    dbres = db_get(query)
    tspec = get_tspec(dbres[0][0])
    if tspec == "":
        if dbres[0][1] is not None:
            tspec = get_tspec_r(dbres[0][1])
    return tspec


def do_ve_coverage(tcs, results):
    """

    :param tcs: test cases results
    :return: coverage
    """
    ntc = len(tcs)
    if ntc == 0:
        coverage = 'NotCovered'
    else:
        tccount = Counter()
        for tc in tcs.keys():
            # if tc in results.keys() and results[tc]['lastR']:
            if tc in results.keys() and 'lastR' in results[tc].keys() and results[tc]['lastR']:
                tccount.update([results[tc]['lastR']['status']])
            else:
                tccount.update(['notexec'])
        if tccount['failed'] and tccount['failed'] > 0:
            coverage = 'WithFailures'
        else:
            if tccount['passed'] + tccount['cndpass'] == ntc:
                coverage = 'FullyVerified'
            else:
                if tccount['notexec'] == ntc:
                    coverage = 'NotVerified'
                else:
                    coverage = 'PartiallyVerified'

    return coverage


def do_req_coverage(ves, ve_coverage):
    """
    Calculate the coverage level of a requirement
    based on the downstram verification elements.
    :param myvreq: version requirement name
    :param ves:
    :param ve_coverage:
    :return:
    """
    nves = len(ves)
    vecount = Counter()
    for ve in ves:
        element = ve_coverage[ve]
        # This implies there is only one VE per requirement (true for now)
        cover = element['coverage']
        vecount.update([cover])
    if vecount['WithFailures'] and vecount['WithFailures'] > 0:
        rcoverage = "WithFailures"
    else:
        if 'FullyVerified' in vecount.keys():
            if vecount['FullyVerified'] == nves:
                rcoverage = "FullyVerified"
            else:
                rcoverage = "PartiallyVerified"
        elif 'PartiallyVerified' in vecount.keys():
            rcoverage = "PartiallyVerified"
        else:
            if vecount["NotCovered"] == nves:
                rcoverage = "NotCovered"
            else:
                rcoverage = 'NotVerified'
    return rcoverage


def find_vekey(reqname, ve_keys):
    """ Look through the keys until we find the one my requirment starts with
    """
    for k in ve_keys:
        if k.startswith(reqname):
            return k


def summary(dictionary):
    """generate and print summary information"""
    global veduplicated
    mtrs = dict()

    verification_elements = dictionary[0]
    reqs = dictionary[1]

    tcases = dictionary[3]

    mtrs['nr'] = len(reqs)
    mtrs['nv'] = len(verification_elements)
    mtrs['nt'] = len(tcases)

    for reqname, req in reqs.items():
        Config.REQ_STATUS_PER_DOC_COUNT.update([req["reqDoc"]])
        Config.REQ_STATUS_PER_DOC_COUNT.update([req["reqDoc"]+"."+req["priority"]])
        for ve in req['VEs']:
            keys = verification_elements[ve].keys()
            verified_by = 'verified_by' in keys
            if verified_by and verification_elements[ve]['verified_by']:
                # I calculate the coverage looking at the test cases
                # associated with the verifying VEs
                vbytcs = dict()
                for vby in verification_elements[ve]['verified_by']:
                    if verification_elements[ve]['tcs']:
                        vbytcs.update(verification_elements[ve]['tcs'])
                    else:
                        print(f'Tests not found for {vby} verifying {ve}.')
                vcoverage = do_ve_coverage(vbytcs, dictionary[3])
            else:
                vcoverage = do_ve_coverage(verification_elements[ve]['tcs'], tcases)
            Config.VE_STATUS_COUNT.update([vcoverage])
            verification_elements[ve]['coverage'] = vcoverage
        # Calculating the requirement coverage based on the VE coverage
        rcoverage = do_req_coverage(req['VEs'], verification_elements)
        Config.REQ_STATUS_COUNT.update([rcoverage])
        Config.REQ_STATUS_PER_DOC_COUNT.update([req["reqDoc"] + ".zAll." + rcoverage])
        Config.REQ_STATUS_PER_DOC_COUNT.update([req["reqDoc"] + "." + req["priority"] + "." + rcoverage])
    for tc in tcases.values():
        if 'lastR' in tc.keys() and tc['lastR']:
            Config.TEST_STATUS_COUNT.update([tc['lastR']['status']])
        else:
            Config.TEST_STATUS_COUNT.update([tc['status']])

    req_coverage = dict()
    for entry in Config.REQ_STATUS_COUNT.items():
        print(entry)
        req_coverage[entry[0]] = entry[1]
    ve_coverage = dict()
    total_ve = 0
    for entry in Config.VE_STATUS_COUNT.items():
        ve_coverage[entry[0]] = entry[1]
        total_ve = total_ve + entry[1]
    tc_status = dict()
    tc_status['NotExecuted'] = 0
    for entry in Config.TEST_STATUS_COUNT.items():
        if entry[0] in ('Draft', 'Approved', 'Defined', 'notexec', 'Deprecated'):
            tc_status['NotExecuted'] = tc_status['NotExecuted'] + entry[1]
        tc_status[entry[0]] = entry[1]
    rec_count_per_doc = dict()
    for entry in Config.REQ_STATUS_PER_DOC_COUNT.items():
        split0 = entry[0].split(".")
        doc = split0[0]
        if doc not in rec_count_per_doc.keys():
            rec_count_per_doc[doc] = dict()
        if len(split0) == 1:
            rec_count_per_doc[doc]['count'] = entry[1]
        else:
            priority = split0[1]
            if priority not in rec_count_per_doc[doc].keys():
                rec_count_per_doc[doc][priority] = dict()
            if len(split0) == 2:
                rec_count_per_doc[doc][priority]['count'] = entry[1]
            else:
                rec_count_per_doc[doc][priority][split0[2]] = entry[1]
    # sorting the priority dictionary
    for doc in rec_count_per_doc.keys():
        tmp_doc = dict()
        for key in sorted(rec_count_per_doc[doc].keys()):
            tmp_doc[key] = rec_count_per_doc[doc][key]
        rec_count_per_doc[doc] = tmp_doc

    size = [len(reqs), total_ve, len(tcases)]

    print(rec_count_per_doc)

    return [tc_status, ve_coverage, req_coverage, rec_count_per_doc, [], [], size]


def check_acronyms(reqs):
    """check that the requirements acronyms have been added to acronyms.tex"""
    acronyms = []
    rtype = []

    acro_file = open("acronyms.tex", 'r')
    acrolines = acro_file.readlines()
    for line in acrolines:
        tmpacro = line.split(" ")
        acronyms.append(tmpacro[0].strip())

    for req in reqs.keys():
        tmptype = req[:-5]
        if tmptype not in rtype:
            rtype.append(tmptype)
            if tmptype not in acronyms:
                print("Missing acronyms", tmptype)


def vcdsql(comp, RSP):
    """get VCD using direct SQL query"""
    global veduplicated
    veduplicated = dict()

    print(f"Looking for VEs in {comp} ...")

    ves, reqs = get_ves(comp)

    print(f"  ... found {len(ves)} Verification Elements "
          f"  related to {len(reqs)} requirements and {len(Config.CACHED_TESTCASES)} test cases.")

    if os.path.isfile("acronyms.tex"):
        check_acronyms(reqs)

    # creating the lookup Specs to Reqs
    for req, values in reqs.items():
        # print(" - ", req)
        if values['reqDoc'] not in Config.REQ_PER_DOC.keys():
            Config.REQ_PER_DOC[values['reqDoc']] = []
        Config.REQ_PER_DOC[values['reqDoc']].append(req)

    # Credit: KTL
    # print out the list of test cases, sorted per requirement priority
    # "*" indicates that the test case the execution result is
    # "Passed" or "Conditinoaly Passed"
    if RSP != "":
        spec_split = RSP.split('|')
        if len(spec_split) == 2:
            req_f = spec_split[0]
            test_f = spec_split[1]
        else:
            req_f = RSP
            test_f = ""
        print(f"Test cases related to {RSP} grouped per priority.\n",
              " '*' indicates that the test case the execution result "
              "is 'Passed' or 'Conditional-Passed'")
        by_priority = {"1a": {}, "1b": {}, "2": {}, "3": {}}
        executed = {}
        for ve in ves.values():
            if ve["Requirement Specification"] == req_f:
                for tc in ve['tcs']:
                    if ve['tcs'][tc]['tspec'] == test_f or test_f == "":
                        tc_number = int(tc[5:])  # strip off LVV-T
                        lastR = ve['tcs'][tc]['lastR']
                        if lastR and "status" in lastR.keys():
                            if lastR["status"] not in ('passed', 'notexec', 'failed'):
                                print(lastR["status"])
                        executed[tc_number] = lastR is not None and (lastR['status'] == "passed" or
                                                                     lastR['status'] == "cndpass")
                        if 'Requirement Priority' in ve.keys():
                            by_priority[ve['Requirement Priority']][tc_number] = 1
                            # print(ve)
                        else:
                            print("No Req Priority for VE", ve["jkey"], ". Looking for VE priority.")
                            if "priority" in ve.keys() and ve['priority'] != "Undefined":
                                by_priority[ve['priority']][tc_number] = 1
        for priority in sorted(by_priority.keys()):
            print(f"Priority: {priority}")
            tc_list = []
            for tc_number in sorted(by_priority[priority].keys()):
                tc_name = f"LVV-T{tc_number}"
                if executed[tc_number]:
                    tc_name += "*"
                tc_list.append(tc_name)
            print(", ".join(tc_list))
        # print REQ Spec requriements in csv file
        csv = "ID, Title, Priority\n"
        # i = 0
        for req in Config.REQ_PER_DOC[req_f]:
            # i = i + 1
            # print(i, req, "\n", reqs[req])
            csv = csv + f"'{req}', '{reqs[req]['reqTitle']}', '{reqs[req]['priority']}'\n"
        csv_filename = req_f.lower() + ".csv"
        file = open(csv_filename, "w")
        print(csv, file=file)
        file.close()

    return [ves, reqs, veduplicated, Config.CACHED_TESTCASES]
