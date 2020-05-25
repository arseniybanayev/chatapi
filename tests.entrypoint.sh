#!/bin/bash

# Wait for a specified host:port to be open if WAIT_FOR is not empty
if [ ! -z "$WAIT_FOR" ] ; then
	IFS=':' read -ra SVC <<< "$WAIT_FOR"
	if [ ${#SVC[@]} -ne 2 ]; then
		echo "\$WAIT_FOR (${WAIT_FOR}) env var should be in form HOST:PORT"
		exit 1
	fi
	until nc -z -v -w5 ${SVC[0]} ${SVC[1]}; do echo "waiting for ${WAIT_FOR}..."; sleep 3; done
fi

# Run the actual command(s)
exec "$@"