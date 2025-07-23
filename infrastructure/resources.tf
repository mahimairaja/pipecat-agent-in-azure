resource "azurerm_resource_group" "rg" {
  name     = "my-foundary-rg"
  location = "eastus"
}

resource "azurerm_storage_account" "sa" {
  name                     = "myfoundarystorage"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_container_registry" "cr" {
  name                = "myfoundaryregistry"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = true
}

resource "azurerm_container_app_environment" "env" {
  name                = "my-foundary-env"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

output "acr_login_server" {
  value = azurerm_container_registry.cr.login_server
}

output "container_app_env_id" {
  value = azurerm_container_app_environment.env.id
} 