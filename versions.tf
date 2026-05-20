terraform {
  required_version = ">= 1.14.3"

  required_providers {
    vsphere = {
      source  = "vmware/vsphere"
      version = "~> 2.15"
    }
  }
}
