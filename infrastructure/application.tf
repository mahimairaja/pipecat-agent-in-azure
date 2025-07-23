resource "azurerm_container_app" "app" {
  name                         = "my-foundary-app"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = azurerm_resource_group.rg.name
  revision_mode                = "Single"

  template {
    container {
      name   = "fastapi-app"
      image  = "${azurerm_container_registry.cr.login_server}/myfoundaryregistry:latest"
      cpu    = 0.5
      memory = "1.0Gi"
      env {
        name  = "PORT"
        value = "8000"
      }
    }
  }

  registry {
    server   = azurerm_container_registry.cr.login_server
    username = azurerm_container_registry.cr.admin_username
  }

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
    transport        = "auto"
  }
} 