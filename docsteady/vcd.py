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
import requests
from marshmallow import Schema, fields, pre_load

from docsteady.cycle import TestCycle, TestResult
from docsteady.spec import Issue, TestCase
from docsteady.utils import owner_for_id, as_arrow, HtmlPandocField, SubsectionableHtmlPandocField, \
    MarkdownableHtmlPandocField, get_tspec
from .config import Config


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
    return(status)

def build_vcd_model(component):
    # build the vcd. Only Verification Issues are considered. 

    fname = component.lower() + "_vcd.tex"

    rs = requests.Session()

    # get component id
    resp = rs.get("https://jira.lsstcorp.org/rest/api/2/project/LVV/components",
                        auth=Config.AUTH)
    cmps = resp.json()
    cId = ''
    for c in cmps:
        if c['name'] == component:
            cId = c['id']
            break
    if cId == '':
        print(f"Error. Component {{c}} not found in LVV project".format(c=component))
        exit()

    # get the number of issue in the componenet
    resp = rs.get(F"https://jira.lsstcorp.org/rest/api/latest/component/{{cid}}/relatedIssueCounts".format(cid=cId),
                        auth=Config.AUTH)
    cmpCount = resp.json()
    maxRes = cmpCount['issueCount']

    print(f"Getting {{maxR}} Verification Elements from {{cmpnt}}.".format(maxR=maxRes, cmpnt=component))
    resp = rs.get(Config.VE_SEARCH_URL.format(cmpnt=component,maxR=maxRes),
                        auth=Config.AUTH)
    resp.raise_for_status()

    velem = {}
    reqs = {}
    tcases = {}

    veresp = resp.json()
    i = 0
    for ve in veresp['issues']:
        i = i + 1
        tmp = {}
        tmp['key'] = ve['key']
        #tmp['summary'] = ve['fields']['summary']
        ves = ve['fields']['summary'].split(':')
        #tmp['veId'] = ves[0]
        tmp['veSummary'] = ves[1]
        tmp['req'] = ve['fields']['customfield_13511']
        tmp['vmethod'] = ve['fields']['customfield_12002']['value']
        tmp['reqDoc'] = ve['fields']['customfield_13703']
        tmp['reqId'] = ve['fields']['customfield_13511']
        #if 'value' not in ve['fields']['customfield_12206'].keys():
        if ve['fields']['customfield_12206'] is None:
        #if 'customfield_12206' not in ve['fields'].keys():
            tmp['vlevel'] = 'None'
        else:
            tmp['vlevel'] = ve['fields']['customfield_12206']['value']
        if tmp['reqId'] not in reqs.keys():
            rtmp = {}
            rtmp['desc'] = ve['fields']['customfield_13513']
            #print(ve['fields']['customfield_13513'])
            rtmp['reqDoc'] = ve['fields']['customfield_13703']
            rtmp['VEs'] = []
            rtmp['VEs'].append(ves[0])
            reqs[ tmp['reqId'] ] = rtmp
        else:
            reqs[ tmp['reqId'] ]['VEs'].append(ves[0])
            
        #print(i, tmp)
        tcraw = rs.get(Config.ISSUETCASES_URL.format(issuekey=tmp['key']),
                       auth=Config.AUTH)
        tcrawj = tcraw.json()
        tmp['tc'] = []
        for tc in tcrawj:
            if tc['key'] not in tmp['tc']:
                tmp['tc'].append(tc['key'])
                #print('     - ',tc['key'])
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
                    tcases[ tc['key'] ] = tctmp
        #print(f"[{{i}} {{ve}} {{veId}} {{vlevel}} ({{ntc}})]  ".format(i=i,ve=tmp['key'], veId=ves[0], vlevel=tmp['vlevel'], ntc=len(tmp['tc'])))
        velem[ ves[0] ] = tmp

    print("\nGot", len(velem), "Verification Elements on", len(reqs), "Requirements. Found", len(tcases), ' related test cases.')

    for tck in tcases.keys():
        #print(tck, end="")
        tcd = rs.get(Config.TESTCASERESULT_URL.format(tcid=tck),
                     auth=Config.AUTH)
        if tcd.status_code == 404:
            #print('(NR)', end="")
            continue
        else:
            tcdj = tcd.json()
            tmpr = {}
            tmpr['status'] = runstatus(tcdj['status'])
            #print('(', tcdj['status'],')', end="")
            tmpr['date'] = tcdj['executionDate'][0:10]
            tmpr['tester'] = tcdj['executedBy']
            tmpr['key'] = tcdj['key']
            if 'comment' in tcdj.keys():
                tmpr['comment'] = tcdj['comment']
            else:
                tmpr['comment'] = ""
            #print(Config.TESTPLANCYCLE_URL.format(trk=tcdj['key']))
            tctp = rs.get(Config.TESTPLANCYCLE_URL.format(trk=tcdj['key']),
                     auth=Config.AUTH)
            tctpj = tctp.json()
            if 'testRun' in tctpj.keys():
                tmpr['tcycle'] = tctpj['testRun']['key']
                if 'testPlan' in tctpj['testRun'].keys():
                    tmpr['tplan'] = tctpj['testRun']['testPlan']['key']
                    tpl = rs.get(Config.TPLANCF_URL.format(tpk=tmpr['tplan']))
                    tplj = tpl.json()
                    tmpr['TPR'] = tplj['customFields']['Document ID']
                else:
                    tmpr['tplan'] = "NA"
                    tmpr['TPR'] = "NA"
            else:
                tmpr['tcycle'] = "NA"
                tmpr['TPR'] = "NA"
                tmpr['tplan'] = "NA"
            tcases[ tck ]['lastResult'] = tmpr
    #print(" -")

    fsum = open("summary.tex", 'w')
    print('\\newpage\n\\section{Summary Information}', file=fsum)    
    print('\\begin{longtable}{ll}\n\\toprule', file=fsum)
    print(f"Number of Requirements: & {{nr}} \\\\".format(nr=len(reqs)), file=fsum)
    print(f"Number of Verification Elements: & {{ne}} \\\\".format(ne=len(velem)), file=fsum)
    print(f"Number of Test Cases: & {{ntc}} \\\\".format(ntc=len(tcases)), file=fsum)
    print('\\bottomrule\n\\end{longtable}', file=fsum)
    fsum.close()

    fout = open(fname, 'w')

    print('\\section{VCD}', file=fout)    
    print('\\afterpage{', file=fout)
    #print('\\begin{landscape}\n', file=fout)
    #print('% Ugly hack for centering on page\n\\null\n\\vspace{1.0cm}', file=fout)

    print('{\small', file=fout)
    print('\\newlength{\\LTcapwidthold}', file=fout)
    print('\\setlength{\\LTcapwidthold}{\\LTcapwidth}', file=fout)
    print('\\setlength{\\LTcapwidth}{\\textheight}', file=fout)

    print('\\begin{longtable}{lllll}', file=fout)
    print("\\caption{", component, "VCD Table.}", file=fout)

    print('\\\\\n\\toprule', file=fout)
    print('\\textbf{Requirement} & \\textbf{Verification Element} & \\textbf{Test Case} & \\textbf{Last Run} & \\textbf{Test Status} \\\\\n',
          file=fout)
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
    for req in reqs.keys():
        print(bt, f"{req} {nl} {ndr}{reqs[req]['reqDoc']}{ccb}", et+" &", file=fout)
        #print("\\begin{tabular}{@{}l@{}}", req, f"\\\\ {\\scriptsize{{doc}} }\end{tabular} &".format(doc=reqs[req]['reqDoc']), file=fout)
        nve = len(reqs[req]['VEs'])
        i = 0
        for ve in reqs[req]['VEs']:
            i = i + 1
            if i != 1:
                print(" & ", file=fout, end='')
            print(bt, f"{ve} {nl} {njr}{velem[ve]['key']}{ccb}", et+" &", file=fout)
            #print("\\begin{tabular}{@{}l@{}}", ve, "\\\\ \\vcdJiraRef{", velem[ve]['key'], "}\\end{tabular} &", file=fout)
            ntc = len(velem[ve]['tc'])
            if ntc == 0:
                print(" && \\\\", file = fout)
            else:
                l = 0
                for tc in velem[ve]['tc']:
                    l = l + 1
                    if l != 1:
                        print(" && ", file=fout, end='')
                    print(bt, f"{atm}testCase/{tc}{ccb}{ocb}{tc}{ccb} {nl} {ndr}{tcases[tc]['tspec']}{ccb}", et+" &", file=fout)
                    #print("\\begin{tabular}{@{}l@{}}", tc, "\\\\ \\vcdDocRef{", tcases[tc]['tspec'], "}\\end{tabular} &", file=fout)
                    #print(f"    _ {{tc}}({{tcs}}) in {{tspec}} test specification".format(tc=tc,tcs=tcases[tc]['status'],tspec=tcases[tc]['tspec']))
                    if 'lastResult' in tcases[tc].keys():
                        print(bt, tcases[tc]['lastResult']['date'], nl, file=fout, end='')
                        #print("\\begin{tabular}{@{}l@{}}", tcases[tc]['lastResult']['date'], " \\\\ ", file=fout, end='')
                        tcy = tcases[tc]['lastResult']['tcycle']
                        if tcases[tc]['lastResult']['TPR'] != "NA":
                            print(f"{ndr}{tcases[tc]['lastResult']['TPR']}{ccb} {scr}{atm}testCycle/{tcy}{ccb}{ocb}{tcy}{ccb} {ccb}", et+" &", file=fout, end='')
                        else:
                            print(f"{scr}NA {atm}{tcy}{ccb}{ocb}{tcy}{ccb} {ccb}", et+" &", file=fout, end='')
                        #    print("\\vcdDocRef{", tcases[tc]['lastResult']['TPR'], "} \\vcdJiraRef{", tcases[tc]['lastResult']['tcycle'], "}\\end{tabular} &", file=fout, end='')
                        #    print("{\\scriptsize ", tcases[tc]['lastResult']['TPR'], tcases[tc]['lastResult']['tcycle'], "}\\end{tabular} &", file=fout, end='')
                        print(f" \\{{result}} \\\\ ".format(result=tcases[tc]['lastResult']['status']), file=fout)
                        #print(f"       Execution date {{date}} ({{doc}})  result: {{result}}".format(date=tcases[tc]['lastResult']['date'],doc=tcases[tc]['lastResult']['tplan'],result=tcases[tc]['lastResult']['status']))
                    else:
                        print(" & \\notexec{} \\\\", file=fout)
                        #print("        Not run")
                    if l != ntc:
                        print("\\cmidrule{3-5}", file=fout)
            if i != nve:
                print("\\cmidrule{2-5}", file=fout)
        print("\\midrule", file=fout)

    print('\\label{tab:dmvcd}', file=fout)
    print('\\end{longtable}', file=fout)
    #print('\\setlength{\\LTcapwidth}{\\LTcapwidthold}', file=fout)
    #print('\\end{landscape}', file=fout)
    print('}\n}', file=fout)
    fout.close()
