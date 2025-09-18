<img alt="gitleaks badge" src="https://img.shields.io/badge/protected%20by-gitleaks-blue"> ![Static Badge](https://img.shields.io/badge/Devops-Deepak%20Venkatram-Green)

# AWS-RESOURCE-SCANNER-DASHBOARD
This python script will report all the resource that a AWS ID is using into a csv file with the information like active/not,inuse/not used etc to make informed decision on the resources. The dashboard help you to visualize the resource in graphs and makes it more presentable. A example of the report is as below

ResourceType	ResourceId	Region	Status	Details	EstimatedMonthlyCost

Requirements.
1. AWS CLI (configured (~/.aws/credentials) and necessary IAM permission to read AWS resources. use the command aws configure, if not configured.
2. Python3.10

Install all these dependencies, simply run the below command
pip install dash pandas plotly streamlit boto3

once installed, run the python application
aws_audit.py

This script scans your AWS account across all regions and collects data for the below resources and generates an output in the same directory as aws_resource_audit_report_full.csv.
1. Unused EBS Volumes
2. Unassociated Elastic IPs
3. S3 buckets & last modified
4. Snapshots
5. AMIs and whether in use
6. EC2 Instances
7. Load Balancers (Classic and ALB/NLB)
8. Fsx file systems
9. EKS Clusters
10. Security Groups (used or not)
11. IAM Users and attached policies

To run the dashboard run the below command; the dashboard is accessablt at localhost:8501.
streamlit run dashboard.py

Open your web browser goto localhost:8501 and upload the generated csv report to visualise the AWS resources.

Note:
This tool does not modify or delete any resources.

It may incur minimal API request charges for services like S3 or EC2 if your AWS plan applies charges for high-volume reads (usually negligible).
All processing is done client-side via boto3.

Additional, enhancement
Find the orphaned/redundent snapshots.
