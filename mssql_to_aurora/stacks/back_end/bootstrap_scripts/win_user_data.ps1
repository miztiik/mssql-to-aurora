<powershell>
#Bastion addons
Import-Module AWSPowerShell
New-NetFirewallRule -DisplayName 'Allow local VPC' -Direction Inbound -LocalAddress 10.0.0.0/8 -LocalPort Any -Action Allow


#domain join with secret from secret manager
[string]$SecretAD  = "ManagedAD-Admin-Password"

</powershell>