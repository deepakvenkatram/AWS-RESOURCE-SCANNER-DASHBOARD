import boto3
import pandas as pd
from datetime import datetime, timezone

report_data = []

def get_all_regions():
    ec2 = boto3.client("ec2")
    response = ec2.describe_regions()
    return [region['RegionName'] for region in response['Regions']]

# 1. Unused EBS Volumes
EBS_PRICE_PER_GB = 0.08  # USD/month (gp3)

def get_unused_ebs_volumes(region):
    ec2 = boto3.client("ec2", region_name=region)
    volumes = ec2.describe_volumes(Filters=[{"Name": "status", "Values": ["available"]}])["Volumes"]
    for vol in volumes:
        size_gb = vol["Size"]
        cost = size_gb * EBS_PRICE_PER_GB
        report_data.append({
            "ResourceType": "EBS Volume",
            "ResourceId": vol["VolumeId"],
            "Region": region,
            "Status": "Unattached",
            "Details": f"Size: {size_gb} GiB",
            "EstimatedMonthlyCostUSD": round(cost, 2)
        })

# 2. Unassociated Elastic IPs
ELASTIC_IP_MONTHLY_COST = 3.60  # USD if unused

def get_unused_elastic_ips(region):
    ec2 = boto3.client("ec2", region_name=region)
    eips = ec2.describe_addresses()["Addresses"]
    for eip in eips:
        if "InstanceId" not in eip:
            report_data.append({
                "ResourceType": "Elastic IP",
                "ResourceId": eip["PublicIp"],
                "Region": region,
                "Status": "Unassociated",
                "Details": "Elastic IP not in use",
                "EstimatedMonthlyCostUSD": ELASTIC_IP_MONTHLY_COST
            })

# 3. S3 Buckets Usage Info (global)
def get_s3_usage_global():
    s3 = boto3.client("s3")
    buckets = s3.list_buckets()["Buckets"]
    for bucket in buckets:
        name = bucket["Name"]
        try:
            region = s3.get_bucket_location(Bucket=name).get("LocationConstraint") or "us-east-1"
            bucket_s3 = boto3.client("s3", region_name=region)
            objects = bucket_s3.list_objects_v2(Bucket=name)
            if "Contents" in objects:
                last_modified = max(obj["LastModified"] for obj in objects["Contents"])
                delta = datetime.now(timezone.utc) - last_modified
                report_data.append({
                    "ResourceType": "S3 Bucket",
                    "ResourceId": name,
                    "Region": region,
                    "Status": "Active",
                    "Details": f"Last Modified: {last_modified.date()}, Unused for {delta.days} days",
                    "EstimatedMonthlyCostUSD": "N/A"
                })
            else:
                report_data.append({
                    "ResourceType": "S3 Bucket",
                    "ResourceId": name,
                    "Region": region,
                    "Status": "Empty",
                    "Details": "No objects in bucket",
                    "EstimatedMonthlyCostUSD": 0
                })
        except Exception as e:
            report_data.append({
                "ResourceType": "S3 Bucket",
                "ResourceId": name,
                "Region": "Unknown",
                "Status": "Error",
                "Details": str(e),
                "EstimatedMonthlyCostUSD": "Error"
            })

# 4. EKS Clusters Info
EKS_CLUSTER_COST = 72.0  # USD/month per control plane

def list_eks_clusters(region):
    eks = boto3.client("eks", region_name=region)
    try:
        cluster_names = eks.list_clusters()["clusters"]
        for name in cluster_names:
            cluster = eks.describe_cluster(name=name)["cluster"]
            report_data.append({
                "ResourceType": "EKS Cluster",
                "ResourceId": name,
                "Region": region,
                "Status": cluster["status"],
                "Details": f"Created at {cluster['createdAt'].date()}",
                "EstimatedMonthlyCostUSD": EKS_CLUSTER_COST
            })
    except Exception as e:
        report_data.append({
            "ResourceType": "EKS Cluster",
            "ResourceId": "N/A",
            "Region": region,
            "Status": "Error",
            "Details": str(e),
            "EstimatedMonthlyCostUSD": "Error"
        })

# 5. FSx Info
FSX_ESTIMATED_GB_COST = 0.40

def list_fsx_usage(region):
    fsx = boto3.client("fsx", region_name=region)
    try:
        filesystems = fsx.describe_file_systems()["FileSystems"]
        for fs in filesystems:
            size_gb = fs.get("StorageCapacity", 0)
            cost = size_gb * FSX_ESTIMATED_GB_COST
            report_data.append({
                "ResourceType": "FSx",
                "ResourceId": fs["FileSystemId"],
                "Region": region,
                "Status": fs["Lifecycle"],
                "Details": f"Created: {fs['CreationTime'].date()}, Size: {size_gb} GiB",
                "EstimatedMonthlyCostUSD": round(cost, 2)
            })
    except Exception as e:
        report_data.append({
            "ResourceType": "FSx",
            "ResourceId": "N/A",
            "Region": region,
            "Status": "Error",
            "Details": str(e),
            "EstimatedMonthlyCostUSD": "Error"
        })

# 6. Snapshots with last modified date
def get_snapshots(region):
    ec2 = boto3.client("ec2", region_name=region)
    snapshots = ec2.describe_snapshots(OwnerIds=['self'])["Snapshots"]
    for snap in snapshots:
        last_modified = snap.get("StartTime")
        report_data.append({
            "ResourceType": "Snapshot",
            "ResourceId": snap["SnapshotId"],
            "Region": region,
            "Status": snap.get("State"),
            "Details": f"StartTime: {last_modified}",
            "EstimatedMonthlyCostUSD": "N/A"
        })

# 7. AMIs and last used (if attached to any instance)
def get_amis(region):
    ec2 = boto3.client("ec2", region_name=region)
    amis = ec2.describe_images(Owners=['self'])['Images']
    
    # Build set of AMIs used by instances
    used_amis = set()
    reservations = ec2.describe_instances()['Reservations']
    for reservation in reservations:
        for instance in reservation['Instances']:
            used_amis.add(instance.get('ImageId'))
    
    for ami in amis:
        ami_id = ami['ImageId']
        creation_date = ami.get('CreationDate', 'N/A')
        last_used = "Yes" if ami_id in used_amis else "No"
        report_data.append({
            "ResourceType": "AMI",
            "ResourceId": ami_id,
            "Region": region,
            "Status": f"Last Used by instance: {last_used}",
            "Details": f"CreationDate: {creation_date}",
            "EstimatedMonthlyCostUSD": "N/A"
        })

# 8. Load Balancers (ALB and Classic ELB)
def get_load_balancers(region):
    elbv2 = boto3.client("elbv2", region_name=region)
    elb = boto3.client("elb", region_name=region)
    
    # ALBs
    try:
        lbs = elbv2.describe_load_balancers()["LoadBalancers"]
        for lb in lbs:
            report_data.append({
                "ResourceType": "Load Balancer (ALB/NLB)",
                "ResourceId": lb["LoadBalancerArn"],
                "Region": region,
                "Status": lb["State"]["Code"],
                "Details": f"Type: {lb['Type']}, DNS: {lb['DNSName']}",
                "EstimatedMonthlyCostUSD": "N/A"  # Last used would require CloudWatch metrics
            })
    except Exception as e:
        report_data.append({
            "ResourceType": "Load Balancer (ALB/NLB)",
            "ResourceId": "N/A",
            "Region": region,
            "Status": "Error",
            "Details": str(e),
            "EstimatedMonthlyCostUSD": "Error"
        })
    
    # Classic ELBs
    try:
        lbs = elb.describe_load_balancers()["LoadBalancerDescriptions"]
        for lb in lbs:
            report_data.append({
                "ResourceType": "Load Balancer (Classic)",
                "ResourceId": lb["LoadBalancerName"],
                "Region": region,
                "Status": "Active",  # Classic ELB doesn't have detailed status in API
                "Details": f"DNS: {lb['DNSName']}",
                "EstimatedMonthlyCostUSD": "N/A"
            })
    except Exception as e:
        report_data.append({
            "ResourceType": "Load Balancer (Classic)",
            "ResourceId": "N/A",
            "Region": region,
            "Status": "Error",
            "Details": str(e),
            "EstimatedMonthlyCostUSD": "Error"
        })

# 9. Security Groups - used vs unused
def get_security_groups(region):
    ec2 = boto3.client("ec2", region_name=region)
    sgs = ec2.describe_security_groups()["SecurityGroups"]
    
    # Find all security groups attached to instances
    attached_sgs = set()
    reservations = ec2.describe_instances()['Reservations']
    for reservation in reservations:
        for instance in reservation['Instances']:
            for sg in instance.get('SecurityGroups', []):
                attached_sgs.add(sg['GroupId'])
    
    for sg in sgs:
        in_use = sg['GroupId'] in attached_sgs
        report_data.append({
            "ResourceType": "Security Group",
            "ResourceId": sg['GroupId'],
            "Region": region,
            "Status": "Used" if in_use else "Unused",
            "Details": f"GroupName: {sg.get('GroupName', '')}, Description: {sg.get('Description', '')}",
            "EstimatedMonthlyCostUSD": "N/A"
        })

# 10. IAM Users and Policies (global)
def get_iam_users_and_policies():
    iam = boto3.client('iam')
    users = iam.list_users()['Users']
    for user in users:
        user_name = user['UserName']
        attached_policies = iam.list_attached_user_policies(UserName=user_name)['AttachedPolicies']
        inline_policies = iam.list_user_policies(UserName=user_name)['PolicyNames']
        policies = [p['PolicyName'] for p in attached_policies] + inline_policies
        report_data.append({
            "ResourceType": "IAM User",
            "ResourceId": user_name,
            "Region": "global",
            "Status": "Active",
            "Details": f"Attached Policies: {policies}",
            "EstimatedMonthlyCostUSD": "N/A"
        })

# 11. EC2 Instances
def get_ec2_instances(region):
    ec2 = boto3.client('ec2', region_name=region)
    reservations = ec2.describe_instances()['Reservations']
    for reservation in reservations:
        for instance in reservation['Instances']:
            instance_id = instance.get('InstanceId')
            instance_type = instance.get('InstanceType')
            state = instance.get('State', {}).get('Name')
            launch_time = instance.get('LaunchTime')
            ami_id = instance.get('ImageId')
            sg_list = [sg['GroupId'] for sg in instance.get('SecurityGroups', [])]

            report_data.append({
                "ResourceType": "EC2 Instance",
                "ResourceId": instance_id,
                "Region": region,
                "Status": state,
                "Details": f"Type: {instance_type}, Launched: {launch_time}, AMI: {ami_id}, SGs: {sg_list}",
                "EstimatedMonthlyCostUSD": "N/A"
            })

def main():
    regions = get_all_regions()
    
    print("Gathering global resources...")
    get_s3_usage_global()
    get_iam_users_and_policies()
    
    for region in regions:
        print(f"Scanning region: {region}")
        get_unused_ebs_volumes(region)
        get_unused_elastic_ips(region)
        list_eks_clusters(region)
        list_fsx_usage(region)
        get_snapshots(region)
        get_amis(region)
        get_load_balancers(region)
        get_security_groups(region)
        get_ec2_instances(region)
    
    df = pd.DataFrame(report_data)
    csv_path = "aws_resource_audit_report_full.csv"
    df.to_csv(csv_path, index=False)
    print(f"✅ Full report saved to {csv_path}")

if __name__ == "__main__":
    main()

