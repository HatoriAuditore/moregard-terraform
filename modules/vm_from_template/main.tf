data "vsphere_network" "net" {
  name          = var.network_name
  datacenter_id = var.datacenter_id
}

data "vsphere_virtual_machine" "tpl" {
  name          = var.template_name
  datacenter_id = var.datacenter_id
}

resource "vsphere_virtual_machine" "this" {
  name             = var.name
  folder           = var.folder
  resource_pool_id = var.resource_pool_id
  datastore_id     = var.datastore_id

  num_cpus = var.cpu == null ? data.vsphere_virtual_machine.tpl.num_cpus : var.cpu
  memory   = var.memory_mb == null ? data.vsphere_virtual_machine.tpl.memory : var.memory_mb

  firmware                = var.firmware
  efi_secure_boot_enabled = var.efi_secure_boot_enabled
  guest_id                = data.vsphere_virtual_machine.tpl.guest_id
  scsi_type               = data.vsphere_virtual_machine.tpl.scsi_type

  wait_for_guest_ip_timeout   = var.wait_for_guest_ip_timeout
  wait_for_guest_net_timeout  = var.wait_for_guest_net_timeout
  wait_for_guest_net_routable = var.wait_for_guest_net_routable

  network_interface {
    network_id   = data.vsphere_network.net.id
    adapter_type = try(data.vsphere_virtual_machine.tpl.network_interface_types[0], "vmxnet3")
  }

  disk {
    label            = "disk0"
    size             = var.root_disk_gb == null ? data.vsphere_virtual_machine.tpl.disks[0].size : var.root_disk_gb
    thin_provisioned = var.thin_provisioned
  }

  clone {
    template_uuid = data.vsphere_virtual_machine.tpl.id

    dynamic "customize" {
      for_each = var.domain != null || var.ipv4_address != null ? [1] : []

      content {
        linux_options {
          host_name = coalesce(var.computer_name, var.name)
          domain    = coalesce(var.domain, "localdomain")
        }

        dynamic "network_interface" {
          for_each = var.ipv4_address != null ? [1] : []

          content {
            ipv4_address = var.ipv4_address
            ipv4_netmask = var.ipv4_network
          }
        }

        ipv4_gateway    = var.ipv4_gateway
        dns_server_list = var.dns_server_list
        dns_suffix_list = var.dns_suffix_list
      }
    }
  }

  lifecycle {
    ignore_changes = [
      clone[0].template_uuid
    ]
  }
}
