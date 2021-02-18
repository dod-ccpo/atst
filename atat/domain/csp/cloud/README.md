# Azure Cloud README

## Best Practices for integrating with the Azure REST API

- include comprehensive docstrings when writing functions that interact with Azure endpoints. Link to endpoint and object documentation when possible

  - For example, when [creating a management group](https://docs.microsoft.com/en-us/rest/api/resources/managementgroups/createorupdate), it might be useful to know that the response body has its [own documentation](https://docs.microsoft.com/en-us/rest/api/resources/managementgroups/createorupdate#azureasyncoperationresults)

- Make our model classes the "seam" between ATAT and Azure nomenclature.

  - Build payload classes so that their properties align with the parameters used in Azure documentation
  - Build response classes so that data is transformed to use identifiers that make sense for ATAT. Call out instances when we stray from Azure naming conventions with comments

    - For example, an endpoint may return a payload with some property `name`, but we understand that in the context of future API calls, it might make more sense to use the name `<object>_id`. Use the name that is preferable to us (`object_id` in this instance), but document this intentional change with a comment.

  - Only store UUIDs or simple string identifiers in a portfolio's CSP data dictionary, and use these identifiers to build the path for "fully pathed" resources

## Hybrid Cloud Provider

In order to ensure that the provisioning of ATAT entities is happening correctly in Azure, we need a cloud provider interface that can perform as much work as is feasible while we are blocked by injunction. The Hybrid Cloud provider accomplishes this task -- in it, steps of provisioning processes are mocked or monkeypatched where needed in order to emulate as close to a production environment as possible.

### Portfolios

By the end of provisioning a Portfolio with the Hybrid Cloud Provider, the following items should be created:

- New entry in the hybrid KeyVault

  - They key for the entry will be a hash of the `tenant_id`, so it won't be readable in the portal.
  - Use the `sha256_hex` function in `atat.utils` to confirm that the key is a hash of the tenant ID that was generated in `create_tenant`

- App Registration named `Hybrid :: <portfolio name> :: ATAT Remote Admin`

  - The app should have one owner: The Hybrid Cloud user

- Management Group named `Hybrid :: <portfolio name>`

  - A policy set "Default JEDI Policy Set" should be assigned
  - A role assignment of "Owner" for the previously-created app registration

- User named `Hybrid <portfolio name>`, as a result of the `create billing owner` step

- In the [AAD -> Roles & Administrators Blade](https://portal.azure.com/#blade/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/RolesAndAdministrators), search for the `Global Administrator` Role. Click on that entry, and look through the assigned users. An entry should appear with the name `Hybrid :: <portfolio name> :: ATAT Remote Admin` and with the `Service Principal` type.

Evidence of the creation of a service principal with a `Global Administrator` role and a Billing Owner can also be found in the [Enterprise Applications Blade](https://portal.azure.com/#blade/Microsoft_AAD_IAM/StartboardApplicationsMenuBlade/AllApps_)

- Find the `Application Types` filter, select `All Application Types`, and click Apply.
- Search for an application named `Hybrid :: <portfolio name> :: ATAT Remote Admin` and select it
- Select `Audit logs` in the navigation pane
- You should see six entries. If you click on them and inspect their details, three should pertain to creating the service principal and setting the `Global Administrator` role, and three should pertain to creating the `Billing Administrator` user
