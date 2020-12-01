#!/usr/bin/env python3

import os
import sys
import json
import argparse
import dictlib
import time
import boto3
import datetime


def json_serialize(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()

def log(msg, *args):
    print(str(int(time.time())) + " " + msg.format(*args))

def paginate(client, method, *args, **kwargs):
    return client.get_paginator(method).paginate(*args, **kwargs)

class StaticWebsite(object):
    session = None
    _resource = None
    _client = None

    def __init__(self, profile=None, domain=None, region=None):
        if None in (profile, domain, region):
            raise Exception("Something isn't coming in right")

        self.domain = domain
        self.region = region
        self.sess_args = dict(profile_name=profile)
        self._sessions = dict()
        self._resource = dictlib.Obj()
        self._client = dictlib.Obj()

    def session(self, region=None):
        if not region:
            region = self.region
        if not self._sessions.get(region):
            self._sessions[region] = boto3.session.Session(region_name=region, **self.sess_args)
        return self._sessions[region]

    def client(self, rtype, region=None):
        if not self._client.get(rtype):
            self._client[rtype] = self.session(region=region).client(rtype)
        return self._client[rtype]

    def resource(self, rtype, region=None):
        if not self._resource.get(rtype):
            self._resource[rtype] = self.session(region=region).resource(rtype)
        return self._resource[rtype]

    def get_buckets(self):
        s3 = self.resource('s3')
        out = dict()
        for bucket in s3.buckets.all():
            out[bucket.name] = bucket
        return out

    def fmt_buckets(self):
        out = ["Current Buckets:"]
        for bucket_name in self.get_buckets():
            out += ["  " + bucket_name]
        return "\n".join(out)

    def create_bucket(self, name, cfg={}):
        buckets = self.get_buckets()
        if buckets.get(name):
            return name

        log("bucket {}", self.domain)
        cfg = dictlib.union(dict(
            Bucket=name,
            ACL='public-read',
            CreateBucketConfiguration=dict(
              LocationConstraint=self.region
            )
        ), cfg)
        res = self.resource('s3').create_bucket(**cfg)
        return res.name

    def get_account_id(self):
        sts = self.client('sts')
        return sts.get_caller_identity().get('Account')

    def create_iam_policy(self, name, policy):
        iam = self.client('iam')
        try:
            iam.create_policy(
                PolicyName=name,
                PolicyDocument=json.dumps(policy))
            log("iam admin policy")
        except iam.exceptions.EntityAlreadyExistsException:
            log("<skip> iam admin policy already exists")
            pass

    def create_s3_policy(self, name, policy):
        log("s3 bucket policy")
        self.client('s3').put_bucket_policy(Bucket=name, Policy=json.dumps(policy))

    def acm_ssl_cert(self, name, region=None):
        acm = self.client('acm', region=region)
        cert_arn = self.acm_get_cert_arn(name, region=region)
        if cert_arn:
            return self.acm_wait_for_cert(cert_arn, region=region)

        log("{} requesting certificate...", name)
        res = acm.request_certificate(
                DomainName=name,
                ValidationMethod='DNS',
                SubjectAlternativeNames=[
                    'www.' + name,
                ],
                IdempotencyToken='samerequest', # only lasts 1 hour
                DomainValidationOptions=[
                    {
                        'DomainName': name,
                        'ValidationDomain': name,
                    },
                ],
                Options={
                    'CertificateTransparencyLoggingPreference': 'ENABLED',
                }
        )
        return self.acm_wait_for_cert(res.get('CertificateArn'), region=region)

    def acm_wait_for_cert(self, arn, region=None):
        acm = self.client('acm', region=region)
        valid = False
        while not valid:
            cert = acm.describe_certificate(CertificateArn=arn)
            status = cert['Certificate']['Status']
            if status == 'ISSUED':
                return arn
            log("certificate status={}...", status)
            time.sleep(30)
        return arn

    def acm_get_cert_arn(self, name, region=None):
        acm = self.client('acm', region=region)
        # NOTE: this doesn't pay attention to NextToken and pagination
        res = acm.list_certificates(CertificateStatuses=['PENDING_VALIDATION', 'ISSUED'])
        for cert in res['CertificateSummaryList']:
            if cert['DomainName'] == name:
                return cert['CertificateArn']
        return None

    def s3_bucket_website(self, name):
        s3 = self.resource('s3')
        website = s3.BucketWebsite(name)
        log("configuring {} as website", name)
        obj = website.put(
          WebsiteConfiguration={
            'ErrorDocument': {
                'Key': 'error.html'
            },
            'IndexDocument': {
                'Suffix': 'index.html'
            },
          }
        )

        # isn't this somewhere on the object?
        log("http://{}.s3-website-{}.amazonaws.com/", name, self.region)

    def create_cdn(self, web_bucket, log_bucket, cert_arn):
        origin = web_bucket + '.s3-website-' + self.region + '.amazonaws.com'
        log("using origin = {}", origin)
        cf = self.client('cloudfront')
        cf.create_distribution(DistributionConfig=dict(
            CallerReference=web_bucket + '.sameone',
            Aliases = dict(Quantity=1, Items=[self.domain]),
            DefaultRootObject='index.html',
            Comment=self.domain + " cdn",
            Enabled=True,
            Origins = dict(
                Quantity = 1,
                Items = [dict(
                    Id = '1',
#                    DomainName = origin,
# this should be working via S3, but is not, so just say custom
                    DomainName = web_bucket + ".s3.amazonaws.com",
                    S3OriginConfig = dict(OriginAccessIdentity = '')
#                    CustomOriginConfig = dict() # OriginAccessIdentity = '')
                )]),
            DefaultCacheBehavior = dict(
                TargetOriginId = '1',
                ViewerProtocolPolicy= 'redirect-to-https',
                TrustedSigners = dict(Quantity=0, Enabled=False),
                ForwardedValues=dict(
                    Cookies = {'Forward':'all'},
                    Headers = dict(Quantity=0),
                    QueryString=False,
                    QueryStringCacheKeys= dict(Quantity=0),
                    ),
                MinTTL=1000),
            Logging=dict(
                Enabled=True,
                Bucket=log_bucket + ".s3.amazonaws.com",
                IncludeCookies=False,
                Prefix='cdn'
            ),
            ViewerCertificate=dict(
                CloudFrontDefaultCertificate=False,
                ACMCertificateArn=cert_arn,
                CertificateSource='acm',
                SSLSupportMethod='sni-only',
                MinimumProtocolVersion='TLSv1.2_2018'
            ),
            PriceClass='PriceClass_100',
            CustomErrorResponses=dict(
                Items=[dict(
                        ErrorCachingMinTTL=300,
                        ErrorCode=404,
                        ResponseCode="404",
                        ResponsePagePath="/error.html"
                    )],
                Quantity=1
            )
        ))

    def report(self, args):
        cf = self.client('cloudfront')
        if not args.distribution:
            for page in paginate(cf, 'list_distributions'):
                for dist in dictlib.dig(page, 'DistributionList.Items'):
                    if args.raw:
                        print(json.dumps(dist, indent=2, sort_keys=True, default=json_serialize))
                    else:
                        print("{Id} {ARN} {DomainName} {Comment}".format(**dist))
