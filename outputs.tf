output "vm_ids" {
  description = "Managed VM IDs by name"
  value       = { for k, m in module.vms : k => m.id }
}

output "vm_names" {
  description = "Names of managed VMs"
  value       = keys(module.vms)
}
