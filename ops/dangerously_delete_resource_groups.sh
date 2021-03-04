#!/bin/bash
resource_groups="$(az group list --query "[? contains(name,'$1')][].{name:name}" -o tsv)"
echo "==> Resource groups found"
echo "$resource_groups"
echo ""
read -p "Should these all be deleted? [y/N] " -n 1 -r do_continue
echo ""

if [[ ! "$do_continue" =~ ^[Yy]$ ]]; then
    echo "!!! Cancelling..."
    exit 0
fi

for i in $resource_groups; do
    echo "deleting ${i}"
    az group delete -n "${i}" --yes --no-wait
done

