terraform {
    required_providers {
        aws = {
            source = "hashicorp/aws"
            version = "~> 6.0"
        }
    }
}

provider "aws" {
    region = "us-east-1"
    profile = "kthwang3"
}

data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-arm64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical
}

data "aws_vpc" "default_vpc" {
    default = true
}

variable "my_ip" {
  type        = string
  description = "Home IP allowed for SSH, in CIDR /32 form"
}

resource "aws_instance" "web" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t4g.nano"

  tags = {
    Name = "callbackagent"
  }
  vpc_security_group_ids = [aws_security_group.allow_tls.id]
  key_name = aws_key_pair.deployer.key_name

  lifecycle {
    ignore_changes = [ami]
  }
}

resource "aws_security_group" "allow_tls" {
    name = "allow_tls"
    description = "Allow TLS inbound traffic and all outbound traffic"
    vpc_id = data.aws_vpc.default_vpc.id
}
resource "aws_vpc_security_group_ingress_rule" "allow_ssh" {
    security_group_id = aws_security_group.allow_tls.id
    cidr_ipv4 = "0.0.0.0/0"
    from_port = 22
    ip_protocol = "tcp"
    to_port = 22
}
resource "aws_vpc_security_group_ingress_rule" "allow_http" {
    security_group_id = aws_security_group.allow_tls.id
    cidr_ipv4 = "0.0.0.0/0"
    from_port = 80
    ip_protocol = "tcp"
    to_port = 80
}
resource "aws_vpc_security_group_ingress_rule" "allow_https" {
    security_group_id = aws_security_group.allow_tls.id
    cidr_ipv4 = "0.0.0.0/0"
    from_port = 443
    ip_protocol = "tcp"
    to_port = 443
}
resource "aws_vpc_security_group_egress_rule" "allow_all_traffic_ipv4" {
  security_group_id = aws_security_group.allow_tls.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1" # semantically equivalent to all ports
}

resource "aws_eip" "my_eip" {
    domain = "vpc"
}

resource "aws_eip_association" "eip_assoc" {
    instance_id = aws_instance.web.id
    allocation_id = aws_eip.my_eip.id
}

resource "aws_key_pair" "deployer" {
    key_name = "callbackagent-key"
    public_key = file("~/.ssh/callbackagent.pub")
}

output "instance_public_ip" {
    value = aws_eip.my_eip.public_ip
}

