locals {
  vm_defaults = {
    for name, vm in var.vms : name => {
      datacenter = coalesce(try(vm.datacenter, null), var.datacenter)
      cluster    = coalesce(try(vm.cluster, null), var.cluster)
      datastore  = coalesce(try(vm.datastore, null), var.datastore)
      vm_folder  = coalesce(try(vm.vm_folder, null), var.vm_folder)
    }
  }
}

data "vsphere_datacenter" "dc" {
  for_each = {
    for datacenter in toset([
      for vm in values(local.vm_defaults) : vm.datacenter
    ]) : datacenter => datacenter
  }

  name = each.value
}

data "vsphere_compute_cluster" "cluster" {
  for_each = {
    for vm_name, vm in local.vm_defaults : vm_name => vm
  }

  name          = each.value.cluster
  datacenter_id = data.vsphere_datacenter.dc[each.value.datacenter].id
}

data "vsphere_datastore" "ds" {
  for_each = {
    for vm_name, vm in local.vm_defaults : vm_name => vm
  }

  name          = each.value.datastore
  datacenter_id = data.vsphere_datacenter.dc[each.value.datacenter].id
}

module "vms" {
  source   = "./modules/vm_from_template"
  for_each = var.vms

  datacenter_id    = data.vsphere_datacenter.dc[local.vm_defaults[each.key].datacenter].id
  resource_pool_id = data.vsphere_compute_cluster.cluster[each.key].resource_pool_id
  datastore_id     = data.vsphere_datastore.ds[each.key].id
  folder           = local.vm_defaults[each.key].vm_folder

  name          = each.key
  template_name = each.value.template
  network_name  = each.value.network
  firmware      = try(each.value.firmware, "efi")

  cpu                     = try(each.value.cpu, null)
  memory_mb               = try(each.value.ram_mb, null)
  root_disk_gb            = try(each.value.root_disk_gb, null)
  thin_provisioned        = try(each.value.thin_provisioned, false)
  efi_secure_boot_enabled = try(each.value.efi_secure_boot_enabled, false)
  computer_name           = try(each.value.computer_name, each.key)
  domain                  = try(each.value.domain, null)
  dns_server_list         = try(each.value.dns_server_list, [])
  dns_suffix_list         = try(each.value.dns_suffix_list, [])
  ipv4_address            = try(each.value.ipv4_address, null)
  ipv4_network            = coalesce(try(each.value.ipv4_network, null), try(each.value.ipv4_netmask, null))
  ipv4_gateway            = try(each.value.ipv4_gateway, null)

  wait_for_guest_ip_timeout   = 0
  wait_for_guest_net_timeout  = 0
  wait_for_guest_net_routable = false
}
