#!/usr/bin/env python
from __future__ import print_function
import argparse

'''
This script allows transfer of DNS from an upstream DNS server via AXFR as
defined in RFC 5936 and submits entries to Route 53 via boto3. It uses the
UPSERT action to either create a record or update the existing one. You can
use it to do a one time transfer of a type of record from the zone you need or
perform a continual sync of DNS from an upstream server, like an Active
Directory server into a Route 53 privte zone without having to run/pay for the
AWS Directory Service for Microsoft AD. It is safe to run this more than once.

The upstream DNS server must be set to allow AXFR requests.  You can test this
by performing: `dig AXFR yourdomain.com @<DNS_Server>`

Usage: `./AXFR2Route53.py -s 1.2.3.4 -d my.dns.example -z Z1234567891011 -t A`

The above example will try a AXFR for my.dns.example aginst 1.2.3.4 for
"A" records and send them to the Hosted zone: Z1234567891011 in batches of
100.
'''


try:
    import boto3
except ImportError:
    raise SystemExit("Please install boto3: pip install boto3")
try:
    from dns import zone as dnszone
    from dns import query
    from dns.rdataclass import *
    from dns.rdatatype import *
    from dns.exception import DNSException
except ImportError:
    raise SystemExit("Please install dnspython: pip install dnspython")


class AXFR2Route53(object):
    ''' Update Route53 with entries from upstream DNS Server. '''
    def __init__(self, options):
        self.options = options
        self.update_records()

    def update_records(self):
        ''' Run route53 updates based on AXFR request '''
        # performing axfr
        try:
            print("Making AXFR request to " + self.options.dns_server + "...")
        except TypeError:
            raise SystemExit("No DNS server set. try again with -s to set the "
                             "server to make the AXFR request against.")
        try:
            z = dnszone.from_xfr(query.xfr(
                self.options.dns_server, self.options.domain))
        except AttributeError:
            raise SystemExit("No domin set. try again with -d to set the "
                             "domain to reuest AXFR request for.")
        if self.options.hostedzone is not None:
            print("AXFR Request recieved a reply from the server."
                  "Preping to send to R53 Hoested Zone: " +
                  str(self.options.hostedzone))
        else:
            raise SystemExit("No Hosted Zone set. try again with -z to set "
                             "the zone to submit the records to.")
        dns_changes = []
        adict = {}
        print("Processing " + str(
            self.options.recordtype) + " records for " + str(
                self.options.domain) + "...")
        if len(z.nodes) == 0:
            raise SystemExit("No records found to "
                             "process... is AXFR enabled the DNS server you "
                             "are pulling from?")
        print("Total records downloaded: " + str(len(z.nodes)))
        if self.options.recordtype == "A":
            rdtypevar = A
            rdclassvar = IN
        elif self.options.recordtype == "AAAA":
            rdtypevar = AAAA
            rdclassvar = IN
        elif self.options.recordtype == "CNAME":
            rdtypevar = CNAME
            rdclassvar = IN
        elif self.options.recordtype == "MX":
            rdtypevar = MX
            rdclassvar = IN
        elif self.options.recordtype == "NS":
            rdtypevar = NS
            rdclassvar = IN
        elif self.options.recordtype == "PTR":
            rdtypevar = PTR
            rdclassvar = IN
        elif self.options.recordtype == "SPF":
            rdtypevar = SPF
            rdclassvar = IN
        elif self.options.recordtype == "TXT":
            rdtypevar = TXT
            rdclassvar = IN
        elif self.options.recordtype == "SRV":
            rdtypevar = SRV
            rdclassvar = IN
        else:
            raise SystemExit("Unknown or unsupported record type "
                             "in Route 53: " + str(self.options.recordtype))
        for name, node in z.nodes.items():
            rdataset = None
            rdataset = node.get_rdataset(
                rdclass=rdclassvar, rdtype=rdtypevar)
            if not rdataset:
                continue
            for rds in rdataset:
                if str(name) == "@":
                    continue
                else:
                    recordname = str(name) + "." + self.options.domain + "."
                    if recordname in adict:
                        ipaddr = str(rds)
                        adict[recordname]['records'].append(ipaddr)
                    else:
                        ipaddr = str(rds)
                        adict[recordname] = {'records': [ipaddr]}
                        adict[recordname].update({'ttl': str(rdataset.ttl)})

        for key, thedict in adict.iteritems():
            ResourceRecordList = []
            for record in thedict['records']:
                ResourceRecordList.append({'Value': record})
            dns_changes.append({'Action': 'UPSERT',
                                'ResourceRecordSet': {
                                    'Name': key,
                                    'Type': self.options.recordtype,
                                    'TTL': int(thedict['ttl']),
                                    'ResourceRecords': ResourceRecordList
                                    }
                                })
        if len(dns_changes) == 0:
            raise SystemExit("No " + self.options.recordtype + " records "
                             "processed... Are there records of this type on "
                             "the DNS server you are pulling from?")
        print("Total records processed: " + str(len(dns_changes)))
        # connecting to route53 via boto
        print("Connecting to Route53 via boto3...")
        client = boto3.client('route53')
        if len(dns_changes) > 98:
            print("Breaking up records into batches of 100 "
                  "to send to Route53...")
            chunks = [dns_changes[x:x+98] for x in xrange(0, len(
                dns_changes), 98)]
            chunkcount = 0
            for chunk in chunks:
                chunkcount = chunkcount + 1
                client.change_resource_record_sets(
                    HostedZoneId=str(self.options.hostedzone),
                    ChangeBatch={'Changes': chunk})
                print("Batch " + str(chunkcount) + " submitted to Route 53")
        else:
            client.change_resource_record_sets(
                HostedZoneId=str(self.options.hostedzone),
                ChangeBatch={'Changes': dns_changes})
            print("Batch 1 submitted to Route 53")


def parser_setup():
    ''' Setup the options parser '''
    desc = 'Performs AXFR request aginst DNS Server and submits to Route53.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('-d',
                        action='store',
                        dest='domain',
                        help='Domain to submit AXFR request for')
    parser.add_argument('-s',
                        action='store',
                        dest='dns_server',
                        help='DNS server to send AXFR request to. '
                             'FQDN is allowed. This ia required.')
    parser.add_argument('-t',
                        action='store',
                        dest='recordtype',
                        default='A',
                        help='Record type to process.')
    parser.add_argument('-c',
                        action='store',
                        dest='comment',
                        default='Managed by AXFR2Route53.py',
                        help='Set Route53 record comment.')
    parser.add_argument('-z',
                        action='store',
                        dest='hostedzone',
                        help='Hosted zone to submit records to. '
                             'This is required.')
    return parser


def main():
    ''' Setup options and call main program '''
    parser = parser_setup()
    options = parser.parse_args()
    AXFR2Route53(options)


if __name__ == '__main__':
    main()
