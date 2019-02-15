#!/bin/sh

# run from inside the container

if [ -z "$AWS_ACCESS_KEY_ID" -o -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "Missing AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY"
    exit 1
fi

echo "using AWS key $AWS_ACCESS_KEY_ID"

cat >> ~/.s3cfg <<END
[default]
access_key=$AWS_ACCESS_KEY_ID
secret_key=$AWS_SECRET_ACCESS_KEY
END

cd /site &&
    s3cmd sync -v -r . s3://$WEB_DOMAIN_BUCKET --delete-removed --acl-grant 'read:*'
