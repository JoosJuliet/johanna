#!/usr/bin/env python3
import json
from argparse import ArgumentParser

from run_common import AWSCli
from run_common import _confirm_phase


def _parse_args():
    parser = ArgumentParser()
    parser.add_argument('-oa', '--origin_bucket_account_id', type=str, required=True, help='origin bucket account id')
    parser.add_argument('-o', '--origin_bucket_name', type=str, required=True, help='origin bucket name')
    parser.add_argument('-ra', '--replication_bucket_account_id', type=str, required=True,
                        help='replication bucket account id')
    parser.add_argument('-r', '--replication_bucket_name', type=str, required=True, help='replication bucket name')
    parser.add_argument('-a', '--replication_aws_access_key', type=str, required=True,
                        help='Replication bucket AWS ACCESS KEY ID')
    parser.add_argument('-s', '--replication_aws_secret_key', type=str, required=True,
                        help='Replication bucket AWS SECRET ACCESS KEY')
    parser.add_argument('-p', '--srr_policy_name', type=str, required=True, help='write down the policy name you want')
    parser.add_argument('-n', '--srr_role_name', type=str, required=True, help='write down the role name you want')

    args = parser.parse_args()

    _confirm_phase()

    return args


def _put_policy_replication_bucket(replication_bucket_name, origin_bucket_account_id):
    aws_cli = AWSCli(aws_access_key=args.replication_aws_access_key,
                     aws_secret_access_key=args.replication_aws_secret_key)

    s3_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "1",
                "Effect": "Allow",
                "Principal": {
                    "AWS": f"arn:aws:iam::{origin_bucket_account_id}:root"
                },
                "Action": [
                    "s3:GetBucketVersioning",
                    "s3:PutBucketVersioning",
                    "s3:ReplicateObject",
                    "s3:ReplicateDelete",
                    "s3:ObjectOwnerOverrideToBucketOwner"
                ],
                "Resource": [
                    f"arn:aws:s3:::{replication_bucket_name}",
                    f"arn:aws:s3:::{replication_bucket_name}/*"
                ]
            }
        ]
    }

    cmd = ['s3api', 'put-bucket-policy',
           '--bucket', replication_bucket_name,
           '--policy', json.dumps(s3_policy)]
    aws_cli.run(cmd)


def run_create_s3_srr_bucket(args):
    aws_cli = AWSCli()

    origin_bucket_name = args.origin_bucket_name
    replication_bucket_name = args.replication_bucket_name
    origin_bucket_account_id = args.origin_bucket_account_id
    replication_bucket_account_id = args.replication_bucket_account_id
    srr_policy_name = args.srr_policy_name
    srr_role_name = args.srr_role_name

    _put_policy_replication_bucket(replication_bucket_name, origin_bucket_account_id)

    s3_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObjectVersionForReplication",
                    "s3:GetObjectVersionAcl"
                ],
                "Resource": [
                    f"arn:aws:s3:::{origin_bucket_name}/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:ListBucket",
                    "s3:GetReplicationConfiguration"
                ],
                "Resource": [
                    f"arn:aws:s3:::{origin_bucket_name}"
                ]
            },
            {
                "Action": [
                    "s3:ReplicateObject",
                    "s3:ReplicateDelete",
                    "s3:ReplicateTags",
                    "s3:GetObjectVersionTagging",
                    "s3:ObjectOwnerOverrideToBucketOwner"
                ],
                "Effect": "Allow",
                "Resource": f"arn:aws:s3:::{replication_bucket_name}/*"
            }
        ]
    }

    cmd = ['iam', 'create-policy']
    cmd += ['--policy-name', srr_policy_name]
    cmd += ['--policy-document', json.dumps(s3_policy)]
    aws_cli.run(cmd, ignore_error=True)

    cc = ['iam', 'create-role']
    cc += ['--role-name', srr_role_name]
    cc += ['--path', '/']
    cc += ['--assume-role-policy-document', 'file://aws_iam/aws-s3-bucket-role.json']
    aws_cli.run(cc)

    cc = ['iam', 'attach-role-policy']
    cc += ['--role-name', srr_role_name]
    cc += ['--policy-arn', f'arn:aws:iam::{origin_bucket_account_id}:policy/{srr_policy_name}']
    aws_cli.run(cc)

    s3_policy = {
        "Role": f"arn:aws:iam::{origin_bucket_account_id}:role/{srr_role_name}",
        "Rules": [
            {
                "Status": "Enabled",
                "Priority": 1,
                "DeleteMarkerReplication": {"Status": "Disabled"},
                "Filter": {"Prefix": ""},
                "Destination": {
                    "Bucket": f"arn:aws:s3:::{replication_bucket_name}",
                    "Account": replication_bucket_account_id,
                    "AccessControlTranslation": {
                        "Owner": "Destination"
                    }
                }
            }
        ]
    }

    cc = ['s3api', 'put-bucket-replication']
    cc += ['--bucket', origin_bucket_name]
    cc += ['--replication-configuration', json.dumps(s3_policy)]
    aws_cli.run(cc)


if __name__ == "__main__":
    args = _parse_args()

    run_create_s3_srr_bucket(args)
