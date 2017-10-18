# AXFR2Route53.py

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
