#!/bin/bash
aws logs describe-log-groups --query 'logGroups[*].logGroupName' --output text | tr '\t' '\n' | while read lg; do
  echo "Deleting: $lg"
  aws logs delete-log-group --log-group-name "$lg"
done
echo "Done."
