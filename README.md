# Git to S3

Configuration and Deployment for a git repo into an S3 bucket with CDN on Cloudfront.

This is for static HTML assets.  Ideally, fingerprinted.

It looks for the content to deploy in `site/` so setup your job such that this is where
your static site ends up being.

## config first

Run script `aws/create-website` -- this creates buckets, ssl cert, CDN and the works.
First argument is the profile to use (~/.aws/credentials) and the second is the domain
for the website.

## maintaning

Setup Github hooks to trigger this job.  If using Jenkins, you can use the Jenkinsfile in repo.
This should work with any CI system that supports docker.

1. Github push to Master triggers a webhook to Jenkins
2. Job `Website Push` (or whatever you call it) is started, which:
    * Context: the job has ~/.aws exported so the job can use it, for privileges
    * The folder `site/` is where the content is pulled from.
    * The container is built with `docker-compose -f docker/deploy/docker-compose.yml build`
    * The container is run (importing privs) with `docker-compose -f docker/deploy/docker-compose.yml run`

