variable "datacenter_id" {
  type = string
}

variable "resource_pool_id" {
  type = string
}

variable "datastore_id" {
  type = string
}

variable "folder" {
  type    = string
  default = null
}

variable "name" {
  type = string
}

variable "template_name" {
  type = string
}

variable "network_name" {
  type = string
}

variable "cpu" {
  type    = number
  default = null
}

variable "memory_mb" {
  type    = number
  default = null

}

variable "root_disk_gb" {
  type    = number
  default = null

}

variable "firmware" {
  type    = string
  default = "efi"
}

variable "computer_name" {
  type    = string
  default = null
}

variable "domain" {
  type    = string
  default = null
}

variable "dns_server_list" {
  type    = list(string)
  default = []
}

variable "dns_suffix_list" {
  type    = list(string)
  default = []
}

variable "ipv4_address" {
  type    = string
  default = null
}

variable "ipv4_network" {
  type    = number
  default = null
}

variable "ipv4_gateway" {
  type    = string
  default = null
}

variable "wait_for_guest_ip_timeout" {
  type    = number
  default = 0
}

variable "wait_for_guest_net_timeout" {
  type    = number
  default = 0
}

variable "wait_for_guest_net_routable" {
  type    = bool
  default = false
}

variable "efi_secure_boot_enabled" {
  type    = bool
  default = false
}

variable "thin_provisioned" {
  type    = bool
  default = false
}
