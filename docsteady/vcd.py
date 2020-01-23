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
import re
from marshmallow import Schema, fields, pre_load, post_load

from .config import Config
from .utils import jhost, jdb, MarkdownableHtmlPandocField, get_tspec, HtmlPandocField


class VerificationE(Schema):
    key = fields.String(required=True)
    summary = HtmlPandocField()
    jira_url = fields.String()
    assignee = fields.String()
    description = HtmlPandocField()
    ve_status = fields.String()
    ve_priority = fields.String()
    req_id = fields.String()
    req_spec = HtmlPandocField()
    req_discussion = HtmlPandocField()
    req_priority = fields.String()
    req_params = HtmlPandocField()
    raw_upper_req = HtmlPandocField()
    upper_reqs = fields.List(fields.String(), missing=list())
    raw_test_cases = HtmlPandocField()
    test_cases = fields.List(fields.String(), missing=list())

    @pre_load(pass_many=False)
    def extract_fields(self, data):
        data_fields = data["fields"]
        data["summary"] = data_fields["summary"]
        data["jira_url"] = Config.ISSUE_UI_URL.format(issue=data["key"])
        data["assignee"] = data_fields["assignee"]["displayName"]
        data["description"] = data['renderedFields']["description"]
        data["ve_status"] = data_fields["status"]["name"]
        data["ve_priority"] = data_fields["priority"]["name"]
        data["req_id"] = data_fields["customfield_15502"]
        data["req_spec"] = data['renderedFields']["customfield_13513"]
        data["req_discussion"] = data['renderedFields']["customfield_13510"]
        data["req_priority"] = data_fields["customfield_15204"]["value"]
        data["req_params"] = data['renderedFields']["customfield_13512"]
        data["raw_upper_req"] = data_fields["customfield_13515"]
        data["raw_test_cases"] = data_fields["customfield_15106"]
        return data


class Coverage_Count:
    """Coverage for Requirements and Verification Elements"""
    notcs = 0
    noexectcs = 0
    failedtcs = 0
    passedtcs = 0
    passedtcs_name = "Passed TCs"
    passedtcs_label = "sec:passedtcs"

    def total_count(self):
        return self.notcs + self.noexectcs + self.failedtcs  + self.passedtcs


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
    global tcases

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
        print(f"Error. Component {{c}} not found in LVV project".format(c=component))
        exit()

    # get the number of issue in the componenet
    resp = rs.get("https://jira.lsstcorp.org/rest/api/latest/component/{component_id}/relatedIssueCounts",
                  auth=Config.AUTH)
    cmp_count: {} = resp.json()
    max_res = cmp_count['issueCount']

    print(f"Getting {max_res} Verification Elements from {component}.")
    resp = rs.get(Config.VE_SEARCH_URL.format(cmpnt=component, maxR=max_res),
                  auth=Config.AUTH)
    resp.raise_for_status()

    velem = {}
    reqs = {}
    tcases = {}

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
                if tc['key'] not in tcases.keys():
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
                    tcases[tc['key']] = tctmp
        velem[ves[0]] = tmp

    print("\nGot", len(velem), "Verification Elements on", len(reqs), "Requirements. Found",
          len(tcases), ' related test cases.')

    for tck in tcases.keys():
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
            tcases[tck]['lastR'] = tmpr
    # print(" -")

    fsum = open("summary.tex", 'w')
    print('\\newpage\n\\section{Summary Information}', file=fsum)
    print('\\begin{longtable}{ll}\n\\toprule', file=fsum)
    print(f"Number of Requirements: & {{nr}} \\\\".format(nr=len(reqs)), file=fsum)
    print(f"Number of Verification Elements: & {{ne}} \\\\".format(ne=len(velem)), file=fsum)
    print(f"Number of Test Cases: & {{ntc}} \\\\".format(ntc=len(tcases)), file=fsum)
    print('\\bottomrule\n\\end{longtable}', file=fsum)
    fsum.close()


def db_get(jc: {}, dbquery) -> {}:
    """returns query result in a 2dim matrix"""
    db = pymysql.connect(jhost, jc['usr'], jc['pwd'], jdb)
    cursor = db.cursor()
    cursor.execute(dbquery)
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


def init_jira_status(jc):
    """initialize jst containing the statuses from Jira"""
    global jst
    jst = dict()
    query = "select id, pname from issuestatus"
    rawst = db_get(jc, query)
    for st in rawst:
        jst[st[0]] = st[1]


def init_priority(jc):
    """initialize jpr containing the priorities from Jira"""
    global jpr
    jpr = dict()
    query = "select id, pname from priority"
    rawst = db_get(jc, query)
    for st in rawst:
        jpr[st[0]] = st[1]


def get_tc_results(jc, tc):
    """return last execution result"""
    results = dict()
    query = ("select rs.name as status, plan.key as tplan, run.key as tcycle, "
             "tr.`EXECUTION_DATE`, cfv.`STRING_VALUE` as dmtr from AO_4D28DD_TEST_CASE tc "
             "join AO_4D28DD_TEST_RESULT tr on tc.`ID` = tr.`TEST_CASE_ID` "
             "join AO_4D28DD_TRACE_LINK lnk on tr.`TEST_RUN_ID` = lnk.`TEST_RUN_ID` "
             "join AO_4D28DD_TEST_RUN run on lnk.`TEST_RUN_ID` = run.`ID` "
             "join AO_4D28DD_TEST_SET plan on lnk.`TEST_PLAN_ID` = plan.id "
             "join AO_4D28DD_RESULT_STATUS rs on tc.`LAST_TEST_RESULT_STATUS_ID` = rs.id "
             "join AO_4D28DD_CUSTOM_FIELD_VALUE cfv on lnk.`TEST_PLAN_ID` = cfv.`TEST_SET_ID` "
             "where tc.key = '" + tc + "' and cfv.`CUSTOM_FIELD_ID`=66 ")
    trdet = db_get(jc, query)
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


def get_tcs(jc, veid):
    """for a given VE (id) return the related test cases
       and populate in parallel the global tcases """
    global tcases
    query = (
            "select tc.key, tc.FOLDER_ID, tc.LAST_TEST_RESULT_STATUS_ID, aos.name from AO_4D28DD_TEST_CASE tc "
            "inner join AO_4D28DD_TRACE_LINK il on tc.id = il.test_case_id "
            "inner join jiraissue ji on il.issue_id = ji.id "
            "inner join AO_4D28DD_RESULT_STATUS aos on tc.status_id = aos.ID "
            "where tc.archived = 0 and ji.id = " + str(veid))
    rawtc = db_get(jc, query)
    tcs = {}
    for tc in rawtc:
        # print(tc)
        if tc[0] not in tcs:
            # tcs.append(tc[0])
            if tc[0] in tcases.keys():
                tcs[tc[0]] = tcases[tc[0]]
            else:
                tcs[tc[0]] = {}
                tcs[tc[0]]['status'] = tc[3]
                tcs[tc[0]]['tspec'] = get_tspec_r(jc, tc[1])
                if tc[2]:
                    tcs[tc[0]]['lastR'] = get_tc_results(jc, tc[0])
                else:
                    tcs[tc[0]]['lastR'] = None
                tcases[tc[0]] = tcs[tc[0]]
    return tcs


def get_ves(comp, jc):
    """gets information for all Verification Elementes for a Component
       it returns also the reqs and test cases related to them"""
    global jst
    global veduplicated
    velements = dict()
    reqs = dict()
    # get all VE for the provided component
    query = ("select ji.issuenum, ji.id, ji.summary, ji.issuestatus, ji.priority from jiraissue ji "
             "inner join nodeassociation na ON ji.id = na.source_node_id "
             "inner join component c on na.`SINK_NODE_ID`=c.id "
             " where ji.project = 12800 and ji.issuetype = 10602 and c.cname='" + comp + "'")
    raw_ves = db_get(jc, query)

    v = 0
    for ve in raw_ves:
        if ve[3] != '11713':  # ignore DESCOPED VEs
            v = v + 1
            tmpve = dict()
            tmpve['jkey'] = 'LVV-' + str(ve[0])
            ves = ve[2].split(':')
            # print(v, ves[0])
            tmpve['status'] = jst[ve[3]]
            if ve[4]:
                tmpve['priority'] = jpr[ve[4]]
            else:
                tmpve['priority'] = "Not Specified"
            # print(tmpve['priority'], ve[4])
            # get VEs that may verify this VE, instead of test cases
            query = ("select ji.issuenum, ji.summary from jiraissue ji "
                     "inner join issuelink il on il.source = ji.id "
                     "where destination = " + str(ve[1]) + " and linktype = 10700 and ji.issuetype = 10602")
            raw_vby = db_get(jc, query)
            if len(raw_vby) > 0:
                vbytmp = []
                for vby in raw_vby:
                    tsum = vby[1].split(':')
                    vbytmp.append(tsum[0])
                tmpve['verifiedby'] = vbytmp
            # get the parent requirement
            query = ("select cf.id, cf.cfname, cvf.textvalue, "
                     "(select customvalue from customfieldoption where id = cvf.stringvalue) "
                     " from customfieldvalue cvf "
                     "inner join customfield cf on cvf.customfield = cf.id "
                     "inner join jiraissue ji on cvf.issue = ji.id "
                     "where ji.id = " + str(ve[1]) + " and cf.id in (13511, 13703, 15204)")
            raw_cfs = db_get(jc, query)
            for cf in raw_cfs:
                if cf[2]:
                    tmpve[cf[1]] = cf[2]
                else:
                    tmpve[cf[1]] = cf[3]
                # print(f">{{p}}< {{v}}".format(p=cf[1],v=tmpve[cf[1]]))
            if tmpve['Requirement ID'] not in reqs.keys():
                # print(tmpve['Requirement ID'])
                rtmp = dict()
                rtmp['reqDoc'] = tmpve['Requirement Specification']
                rtmp['VEs'] = []
                rtmp['VEs'].append(ves[0])
                if "Requirement Priority" in tmpve.keys():
                    rtmp['priority'] = tmpve['Requirement Priority']
                else:
                    rtmp['priority'] = "Not Set"
                # if rtmp['reqDoc'] == 'LSE-61':
                #    print(tmpve['Requirement ID'], rtmp['reqDoc'], rtmp['priority'])
                reqs[tmpve['Requirement ID']] = rtmp
            else:
                if ves[0] not in reqs[tmpve['Requirement ID']]['VEs']:
                    reqs[tmpve['Requirement ID']]['VEs'].append(ves[0])
            tmpve['tcs'] = []
            tmpve['tcs'] = get_tcs(jc, ve[1])
            # print(tmpve['jkey'], tmpve['tcs'])
            if ves[0] in velements.keys():
                print("  Duplicated:", ves[0], tmpve['jkey'])
                print("    existing:", velements[ves[0]]['jkey'])
                veduplicated[tmpve['jkey']] = velements[ves[0]]['jkey']
            else:
                velements[ves[0]] = tmpve

    return velements, reqs


def get_tspec_r(jc, fid):
    """recursively browse the folders until finding the test spec of the root (NULL)"""
    query = "select name, parent_id from AO_4D28DD_FOLDER where id = " + str(fid)
    # print(query)
    dbres = db_get(jc, query)
    tspec = get_tspec(dbres[0][0])
    if tspec == "":
        if dbres[0][1] is not None:
            tspec = get_tspec_r(jc, dbres[0][1])
    return tspec


def summary(dictionary, comp, user, passwd):
    """generate and print summary information"""
    global tcases
    global jst
    global veduplicated
    mtrs = dict()

    jc = {"usr": user, "pwd": passwd}
    init_jira_status(jc)

    verification_elements = dictionary[0]

    reqs = dictionary[1]

    mtrs['nr'] = len(reqs)
    mtrs['nv'] = len(verification_elements)
    mtrs['nt'] = len(tcases)

    # get TC status and result
    # metric testcases results
    # [ 'Not Executed', 'Pass', 'Fail', 'In Progress', 'Conditional Pass', 'Blocked', 'Unknown' ]
    mtcres = [0, 0, 0, 0, 0, 0, 0]
    # metric testcases status:
    mtcstatus = {"count": [0, 0, 0, 0],
                 "name": ['Draft', 'Defined', 'Approved', 'Deprecated'],
                 "id": [0, 1, 2, 3]}
    for tc in tcases.keys():
        if not tcases[tc]['lastR']:  # not executed
            mtcres[0] += 1
        else:
            if not tcases[tc]['lastR']['status']:
                mtcres[0] += 1
            elif tcases[tc]['lastR']['status'] == "notexec":
                mtcres[0] += 1
            elif tcases[tc]['lastR']['status'] == "passed":
                mtcres[3] += 1
            elif tcases[tc]['lastR']['status'] == "failed":
                mtcres[2] += 1
            elif tcases[tc]['lastR']['status'] == "inprogress":
                mtcres[0] += 1
            elif tcases[tc]['lastR']['status'] == "cndpass":
                mtcres[1] += 1
            elif tcases[tc]['lastR']['status'] == "blocked":
                mtcres[0] += 1
            else:
                print('Unknown test case result:', tcases[tc]['lastR']['status'])
                mtcres[6] += 1
        if tcases[tc]['status'] == 'Draft':
            mtcstatus["count"][0] += 1
        elif tcases[tc]['status'] == 'Defined':
            mtcstatus["count"][1] += 1
        elif tcases[tc]['status'] == 'Approved':
            mtcstatus["count"][2] += 1
        elif tcases[tc]['status'] == 'Deprecated':
            mtcstatus["count"][3] += 1
        else:
            print('Test case status unknown:', tcases[tc]['status'])

    # get VE versus status
    query = ("select ji.issuestatus, count(*) from jiraissue ji "
             "inner join nodeassociation na ON ji.id = na.source_node_id "
             "inner join component c on na.`SINK_NODE_ID`=c.id "
             " where ji.project = 12800 and ji.issuetype = 10602 and c.cname='" + comp + "' group by ji.issuestatus")
    ve_status = db_get(jc, query)
    t = 0
    for s in ve_status:
        ve_status[t].append(jst[s[0]])
        t += 1
    ve_status.append(['-1', len(veduplicated), "Duplicated"])

    # get VE real coverage
    # for reference: cover_names = ['No Test Cases Related', 'No Test Cases Executed', 'Test Cases Partially Executed',
    #               'Some Test Cases Fails', 'All Test Cases Pass', 'All Test Cases Fails']
    ve_coverage = Coverage_Count()
    vestatus = dict()
    for ve in verification_elements.keys():
        tcs = [0, 0, 0, 0]
        ntc = len(verification_elements[ve]['tcs'])
        if 'verifiedby' in verification_elements[ve].keys():
            for sve in verification_elements[ve]['verifiedby']:
                ntc = ntc + len(verification_elements[sve]['tcs'])
                if len(verification_elements[sve]['tcs']) > 0:
                    # 'Not Executed', 'Pass', 'Fail', 'In Progress', 'Conditional Pass', 'Blocked'
                    for tc in verification_elements[sve]['tcs']:
                        if not tcases[tc]['lastR']:  # not executed
                            tcs[0] += 1
                        else:
                            if not tcases[tc]['lastR']['status']:
                                tcs[0] += 1
                            elif tcases[tc]['lastR']['status'] == "notexec":
                                tcs[0] += 1
                            elif tcases[tc]['lastR']['status'] == "passed":
                                tcs[3] += 1
                            elif tcases[tc]['lastR']['status'] == "failed":
                                tcs[2] += 1
                            elif tcases[tc]['lastR']['status'] == "inprogress":
                                tcs[0] += 1
                            elif tcases[tc]['lastR']['status'] == "cndpass":
                                tcs[1] += 1
                            elif tcases[tc]['lastR']['status'] == "blocked":
                                tcs[0] += 1
                            else:
                                print('Unknown Test Case result: ', tcases[tc]['lastR']['status'])
                                tcs[0] += 1
        if ntc == 0:
            ve_coverage.notcs += 1
            vestatus[ve] = Config.coverage_texts['notcs']['name']
        else:
            if len(verification_elements[ve]['tcs']) > 0:
                # 'Not Executed', 'Pass', 'Fail', 'In Progress', 'Conditional Pass', 'Blocked'
                for tc in verification_elements[ve]['tcs']:
                    if not tcases[tc]['lastR']:  # not executed
                        tcs[0] += 1
                    else:
                        # print("  - ", tcases[tc]['lastR'])
                        if not tcases[tc]['lastR']['status']:
                            tcs[0] += 1
                        elif tcases[tc]['lastR']['status'] == "notexec":
                            tcs[0] += 1
                        elif tcases[tc]['lastR']['status'] == "passed":
                            tcs[3] += 1
                        elif tcases[tc]['lastR']['status'] == "failed":
                            tcs[2] += 1
                        elif tcases[tc]['lastR']['status'] == "inprogress":
                            tcs[0] += 1
                        elif tcases[tc]['lastR']['status'] == "cndpass":
                            tcs[1] += 1
                        elif tcases[tc]['lastR']['status'] == "blocked":
                            tcs[0] += 1
                        else:
                            print('Unknown Test Case result: ', tcases[tc]['lastR']['status'])
                            tcs[0] += 1
            if tcs[2] > 0:  # some test cases are failing
                ve_coverage.failedtcs += 1
                vestatus[ve] = Config.coverage_texts['failedtcs']['name']
            elif tcs[3] > 0 or tcs[1] > 0:  # some test cases are passing or conditionally passing
                ve_coverage.passedtcs += 1
                vestatus[ve] = Config.coverage_texts['passedtcs']['name']
            else:  # all other conditions
                ve_coverage.noexectcs += 1
                vestatus[ve] = Config.coverage_texts['noexectcs']['name']

    # get requirements status
    reqcoverage = [0, 0, 0, 0]
    req1acoverage = [0, 0, 0, 0]  # for LSE-61 1a requirements
    reqs_lse61 = []
    reqs_lse61_1a = []
    for req in reqs.keys():
        # 'No Test Cases Related', 'No Test Cases Executed', 'Test Cases Partially Executed',
        # 'Some Test Cases Fails', 'All Test Cases Pass', 'All Test Cases Fails'
        reqves = [0, 0, 0, 0]
        for ve in reqs[req]['VEs']:
            if vestatus[ve] == Config.coverage[0]["name"]:
                reqves[0] += 1  # no TCs
            elif vestatus[ve] == Config.coverage[1]["name"]:
                reqves[1] += 1  # no TCs executed
            elif vestatus[ve] == Config.coverage[2]["name"]:
                reqves[2] += 1  # Failed TCs
            elif vestatus[ve] == Config.coverage[3]["name"]:
                reqves[3] += 1  # Passed TCs
            else:
                reqves[0] += 1  # if not in the above
        if reqves[2] > 0:  # with Failures
            reqcoverage[2] += 1
        elif reqves[3] > 0:  # with Passed
            reqcoverage[3] += 1
        elif reqves[1] > 0:  # no test cases have been executed
            reqcoverage[1] += 1
        else:  # all other cases
            reqcoverage[0] += 1
        if reqs[req]['reqDoc'] == 'LSE-61':
            reqs_lse61.append(req)
            if reqs[req]['priority'] == "1a":
                reqs_lse61_1a.append(req)
                if reqves[2] > 0:  # with Failures
                    req1acoverage[2] += 1
                elif reqves[3] > 0:  # with Passed
                    req1acoverage[3] += 1
                elif reqves[1] > 0:  # no test cases have been executed
                    req1acoverage[1] += 1
                else:  # all other cases
                    reqcoverage[0] += 1

    size = [len(reqs), len(verification_elements), len(tcases), len(reqs_lse61_1a)]

    print(ve_coverage.notcs, ve_coverage.noexectcs, ve_coverage.failedtcs, ve_coverage.passedtcs,
          ve_coverage.total_count())

    return [mtcres, mtcstatus, ve_coverage, ve_status, reqcoverage, req1acoverage, size]


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


def vcdsql(comp, usr, pwd, RSP):
    """get VCD using direct SQL query"""
    global jst
    global jpr
    global tcases
    global veduplicated
    veduplicated = dict()
    tcases = {}

    print(f"Looking for VEs in {comp} ...")
    jcon = {"usr": usr,
            "pwd": pwd}
    init_jira_status(jcon)
    init_priority(jcon)

    ves, reqs = get_ves(comp, jcon)

    print(f"  ... found {{nve}} Verification Elements related to {{nr}} requirements and {{ntc}} test cases.".
          format(nve=len(ves), nr=len(reqs), ntc=len(tcases)))

    check_acronyms(reqs)

    # Credit: KTL
    # print out the list of test cases, sorted per corresponding requirement priority
    # "*" indicates that the test case the execution result is "Passed" or "Conditinoaly Passed"
    if RSP != "":
        spec_split = RSP.split('|')
        if len(spec_split) == 2:
            req_f = spec_split[0]
            test_f = spec_split[1]
        else:
            req_f = RSP
            test_f = ""
        print(f"Test cases related to {{spec}} grouped per priority.\n".format(spec=RSP),
              " '*' indicates that the test case the execution result is 'Passed' or 'Conditinoal-Passed'")
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
                        executed[tc_number] = lastR is not None and (
                        lastR['status'] == "passed" or lastR['status'] == "cndpass")
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

    return [ves, reqs, veduplicated, tcases]
