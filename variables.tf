variable "vsphere_server" {
  type        = string
  description = "vCenter FQDN or IP"
}

variable "vsphere_user" {
  type        = string
  description = "Username for vCenter"
}

variable "vsphere_password" {
  type        = string
  sensitive   = true
  description = "Password for vCenter"
}

variable "allow_unverified_ssl" {
  type        = bool
  default     = false
  description = "Set true only for lab or self-signed TLS"
}

variable "datacenter" {
  type        = string
  default     = null
  description = "vSphere datacenter name"
}

variable "cluster" {
  type        = string
  default     = null
  description = "vSphere compute cluster name"
}

variable "datastore" {
  type        = string
  default     = null
  description = "vSphere datastore name"
}

variable "vm_folder" {
  type        = string
  default     = null
  description = "Folder relative to datacenter VM folder. Null means default location."
}

variable "vms" {
  description = "Map of VMs to create, keyed by VM name"

  type = map(object({
    datacenter              = optional(string)
    cluster                 = optional(string)
    datastore               = optional(string)
    vm_folder               = optional(string)
    template                = string
    network                 = string
    cpu                     = optional(number)
    ram_mb                  = optional(number)
    root_disk_gb            = optional(number)
    firmware                = optional(string, "efi")
    thin_provisioned        = optional(bool, false)
    efi_secure_boot_enabled = optional(bool, false)
    computer_name           = optional(string)
    domain                  = optional(string)
    dns_server_list         = optional(list(string), [])
    dns_suffix_list         = optional(list(string), [])
    ipv4_address            = optional(string)
    ipv4_network            = optional(number)
    ipv4_netmask            = optional(number)
    ipv4_gateway            = optional(string)
  }))

  validation {
    condition = alltrue([
      for name, vm in var.vms : (
        (try(vm.ipv4_address, null) == null &&
        coalesce(try(vm.ipv4_network, null), try(vm.ipv4_netmask, null)) == null) ||
        (try(vm.ipv4_address, null) != null &&
        coalesce(try(vm.ipv4_network, null), try(vm.ipv4_netmask, null)) != null)
      )
    ])
    error_message = "Static IPv4 customization requires ipv4_address and either ipv4_network or ipv4_netmask."
  }
}
