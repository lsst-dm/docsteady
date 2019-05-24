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
from marshmallow import Schema, fields, pre_load

from docsteady.utils import MarkdownableHtmlPandocField, get_tspec
from .config import Config
from .utils import jhost, jdb


class VerificationE(Schema):
    key = fields.String(required=True)
    summary = MarkdownableHtmlPandocField()
    jira_url = fields.String()

    @pre_load(pass_many=False)
    def extract_fields(self, data):
        data_fields = data["fields"]
        data["summary"] = data_fields["summary"]
        data["jira_url"] = Config.ISSUE_UI_URL.format(issue=data["key"])
        return data


def runstatus(trs):
    if trs == "Pass":
        status = 'passed'
    elif trs == "Conditional Pass":
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

    print_vcd(velem, reqs, component)


#
# returns query result in a 2dim matrix 
#
def db_get(jc: {}, dbquery) -> {}:
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


#
#  initialize jst containing the statuses from Jira
#
def init_jira_status(jc):
    global jst
    jst = dict()
    query = "select id, pname from issuestatus"
    rawst = db_get(jc, query)
    for st in rawst:
        jst[st[0]] = st[1]


# return last execution result
#
def get_tc_results(jc, tc):
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
    # print(">>>> ", tc)
    # print(query)
    # print(' - ', trdet)
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
    # print("    -    ", tc, R)
    return results


#
# for a given VE (id) return the related test cases
#   and populate in parallel the global tcases
#
def get_tcs(jc, veid):
    global tcases
    query = (
            "select tc.key, tc.FOLDER_ID, tc.LAST_TEST_RESULT_STATUS_ID from AO_4D28DD_TEST_CASE tc "
            "inner join AO_4D28DD_TRACE_LINK il on tc.id = il.test_case_id "
            "inner join jiraissue ji on il.issue_id = ji.id "
            "where ji.id = " + str(veid))
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
                tcs[tc[0]]['tspec'] = get_tspec_r(jc, tc[1])
                if tc[2]:
                    tcs[tc[0]]['lastR'] = get_tc_results(jc, tc[0])
                else:
                    tcs[tc[0]]['lastR'] = None
                tcases[tc[0]] = tcs[tc[0]]
    return tcs


#
# gets information for all Verification Elementes for a Component
# it returns also the reqs and test cases related to them
#
def get_ves(comp, jc):
    global jst
    velements = dict()
    reqs = dict()
    query = ("select ji.issuenum, ji.id, ji.summary, ji.issuestatus from jiraissue ji "
             "inner join nodeassociation na ON ji.id = na.source_node_id "
             "inner join component c on na.`SINK_NODE_ID`=c.id "
             " where ji.project = 12800 and ji.issuetype = 10602 and c.cname='" + comp + "'")
    raw_ves = db_get(jc, query)

    v = 0
    for ve in raw_ves:
        v = v + 1
        tmpve = dict()
        tmpve['jkey'] = 'LVV-' + str(ve[0])
        ves = ve[2].split(':')
        # print(v, ves[0])
        tmpve['status'] = jst[ve[3]]
        query = ("select cf.id, cf.cfname, cvf.textvalue from customfieldvalue cvf "
                 "inner join customfield cf on cvf.customfield = cf.id "
                 "inner join jiraissue ji on cvf.issue = ji.id "
                 "where ji.id = " + str(ve[1]) + " and cf.id in (13511, 13703)")
        raw_cfs = db_get(jc, query)
        for cf in raw_cfs:
            tmpve[cf[1]] = cf[2]
        if tmpve['Requirement ID'] not in reqs.keys():
            # print(tmpve['Requirement ID'])
            rtmp = dict()
            rtmp['reqDoc'] = tmpve['Requirement Specification']
            rtmp['VEs'] = []
            rtmp['VEs'].append(ves[0])
            reqs[tmpve['Requirement ID']] = rtmp
        else:
            reqs[tmpve['Requirement ID']]['VEs'].append(ves[0])
        tmpve['tcs'] = []
        tmpve['tcs'] = get_tcs(jc, ve[1])
        # print(tmpve['jkey'], tmpve['tcs'])
        if ves[0] in velements.keys():
            print("  Duplicated:", ves[0], tmpve['jkey'])
            print("    existing:", velements[ves[0]]['jkey'])
        else:
            velements[ves[0]] = tmpve
    return velements, reqs


#
# recursivelly browse the folders until findind the test spec of the root (NULL)
#
def get_tspec_r(jc, fid):
    query = "select name, parent_id from AO_4D28DD_FOLDER where id = " + str(fid)
    # print(query)
    dbres = db_get(jc, query)
    tspec = get_tspec(dbres[0][0])
    if tspec == "":
        if dbres[0][1] is not None:
            tspec = get_tspec_r(jc, dbres[0][1])
    return tspec


#
# generate and print summary information
#
def summary(jc, verification_elements, reqs, comp):
    global tcases
    global jst
    mtrs = dict()
    mtrs['nr'] = len(reqs)
    mtrs['nv'] = len(verification_elements)
    mtrs['nt'] = len(tcases)

    # get VE versus status
    query = ("select ji.issuestatus, count(*) from jiraissue ji "
             "inner join nodeassociation na ON ji.id = na.source_node_id "
             "inner join component c on na.`SINK_NODE_ID`=c.id "
             " where ji.project = 12800 and ji.issuetype = 10602 and c.cname='" + comp + "'")
    ve_status = db_get(jc, query)

    # get TC versus status

    # get TC result

    fsum = open(comp.lower() + "_summary.tex", 'w')
    print('\\newpage\n\\section{Summary Information}\\label{sec:summary}', file=fsum)

    # print('\\begin{longtable}{ll}\n\\toprule', file=fsum)
    print('\\begin{longtable}{rccc}\n\\toprule', file=fsum)
    print(
        " & \\textbf{Requirements} & \\textbf{Verification Elements} & \\textbf{Test Cases} \\\\ \\hline",
        file=fsum)
    print(f"N.& {mtrs['nr']} & {mtrs['nv']} & {mtrs['nt']} \\\\", file=fsum)
    # print(f"Number of Requirements: & {mtrs['nr']} \\\\", file=fsum)
    # print(f"Number of Verification Elements: & {mtrs['nv']} \\\\", file=fsum)
    # print(f"Number of Test Cases: & {mtrs['nt']} \\\\", file=fsum)
    print('\\bottomrule\n\\end{longtable}', file=fsum)

    print('\\begin{longtable}{rl}\n\\toprule', file=fsum)
    print("\\multicolumn{2}{c}{\\textbf{Verification Element Status}} \\\\ \\hline", file=fsum)
    t = 0
    for s in ve_status:
        #print(jst[s[0]], s[1])
        t = t + s[1]
        print(f" {jst[s[0]]} & {s[1]} \\\\", file=fsum)
    print("\\hline\n\\textbf{subtotal} & ", f"{t} \\\\", file=fsum)
    print('\\bottomrule\n\\end{longtable}', file=fsum)
    fsum.close()


#
#  print VCD
#
def print_vcd(verification_elements, reqs, comp):
    global tcases
    rtype = []

    fname = comp.lower() + "_vcd.tex"
    fout = open(fname, 'w')
    print('\\section{VCD}\\label{sec:vcd}', file=fout)
    print('\\afterpage{', file=fout)
    print('{\\small', file=fout)
    print('\\newlength{\\LTcapwidthold}', file=fout)
    print('\\setlength{\\LTcapwidthold}{\\LTcapwidth}', file=fout)
    print('\\setlength{\\LTcapwidth}{\\textheight}', file=fout)
    print('\\begin{longtable}{lllll}', file=fout)
    print("\\caption{", comp, "VCD Table.}", file=fout)
    print('\\\\\n\\toprule', file=fout)
    print('\\textbf{Requirement} & \\textbf{Verification Element} & \\textbf{Test Case} & ' +
          '\\textbf{Last Run} & \\textbf{Test Status} \\\\\n', file=fout)
    print('\\toprule\n\\endhead', file=fout)
    bt = '\\begin{tabular}{@{}l@{}}'
    nl = '\\\\'
    njr = '\\vcdJiraRef{'
    ndr = '\\vcdDocRef{'
    ocb = '{'
    ccb = '}'
    et = '\\end{tabular}'
    atm = '\\href{https://jira.lsstcorp.org/secure/Tests.jspa\\#/'
    scr = '{\\scriptsize '
    r = 0
    for req in reqs.keys():
        r = r + 1
        tmptype = req[:-5]
        if tmptype not in rtype:
            rtype.append(tmptype)
        # print(r, req, reqs[req]['reqDoc'])
        print(bt, f"{req} {nl} {ndr}{reqs[req]['reqDoc']}{ccb}", et + " &", file=fout)
        #print(reqs[req])
        nve = len(reqs[req]['VEs'])
        v = 0
        for ve in reqs[req]['VEs']:
            v = v + 1
            # print("    ", v, ve, verification_elements[ve]['jkey'])
            if v != 1:
                print(" & ", file=fout, end='')
            print(bt, f"{ve} {nl} {njr}{verification_elements[ve]['jkey']}{ccb}", et + " &", file=fout)
            ntc = len(verification_elements[ve]['tcs'])
            if ntc == 0:
                print(" && \\\\", file=fout)
            else:
                t = 0
                for tc in verification_elements[ve]['tcs']:
                    t = t + 1
                    # print("        ", t, tc, verification_elements[ve]['tcs'][tc]['tspec'])
                    if t != 1:
                        print(" && ", file=fout, end='')
                    print(bt, f"{atm}testCase/{tc}{ccb}{ocb}{tc}{ccb} {nl} " +
                          f"{ndr}{verification_elements[ve]['tcs'][tc]['tspec']}{ccb}",
                          et + " &", file=fout)
                    # if verification_elements[ve]['tcs'][tc]['lastR']:
                    if not tcases[tc]['lastR']:
                        print(" & \\notexec{} \\\\", file=fout)
                    else:
                        print(bt, tcases[tc]['lastR']['exdate'], nl, file=fout, end='')
                        tpl = tcases[tc]['lastR']['tplan']
                        if tpl != "NA":
                            print(f"{ndr}{tcases[tc]['lastR']['dmtr']}{ccb}" +
                                  f" {scr}{atm}testPlan/{tpl}{ccb}{ocb}{tpl}{ccb} {ccb}",
                                  et + " &", file=fout, end='')
                        else:
                            tcy = tcases[tc]['lastR']['tcycle']
                            print(f"{scr}{atm}testCycle/{tcy}{ccb}{ocb}{tcy}{ccb} {ccb}", et + " &", file=fout, end='')
                        print(f" \\{{result}} \\\\ ".format(result=tcases[tc]['lastR']['status']), file=fout)
                    # else:
                    #    print(" & \\notexec{} \\\\", file=fout)
                    if t != ntc:
                        print("\\cmidrule{3-5}", file=fout)
            if v != nve:
                print("\\cmidrule{2-5}", file=fout)
        print("\\midrule", file=fout)
    print('\\label{tab:dmvcd}', file=fout)
    print('\\end{longtable}', file=fout)
    print('}\n}', file=fout)
    fout.close()

    print("Check that following strings are defined in myacronyms.tex")
    for rt in rtype:
        print("   - ", rt)


#
# get VCD using direct SQL quiery
# 
def vcdsql(comp, usr, pwd):
    global jst
    global tcases
    tcases = {}

    print(f"Looking for VEs in {comp} ...")
    jcon = {"usr": usr,
            "pwd": pwd}
    init_jira_status(jcon)

    ves, reqs = get_ves(comp, jcon)

    print(f"  ... found {{nve}} Verification Elements related to {{nr}} requirements and {{ntc}} test cases.".
          format(nve=len(ves), nr=len(reqs), ntc=len(tcases)))

    print_vcd(ves, reqs, comp)

    summary(jcon, ves, reqs, comp)
