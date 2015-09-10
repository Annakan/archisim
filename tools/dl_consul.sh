#!/usr/bin/env bash
SCRIPTPATH=$( cd "$(dirname "$0")" ; pwd -P )
echo $SCRIPTPATH
mkdir -p $SCRIPTPATH/../consul
pushd $SCRIPTPATH/../consul

CVER="0.5.2"
CONSUL64="${CVER}_linux_amd64.zip"
echo $CONSUL64
CONSUL32="${CVER}_linux_386.zip"
echo $CONSUL32
WEBUI="${CVER}_web_ui.zip"
echo "$WEBUI"
echo "---------------------------------------------"
if [ !  -e "consul64" ]
then
    echo https://dl.bintray.com/mitchellh/consul/${CONSUL64}
    wget -q https://dl.bintray.com/mitchellh/consul/${CONSUL64} -O ${CONSUL64}
    unzip ${CONSUL64}
    mv consul consul64
fi

if [ !  -e "consul32" ]
then
    wget -q https://dl.bintray.com/mitchellh/consul/${CONSUL32} -O ${CONSUL32}
    unzip ${CONSUL32}
    mv consul consul32
fi

if [ !  -e "$WEBUI" ]
then
    wget -q https://dl.bintray.com/mitchellh/consul/${WEBUI} -O ${WEBUI}
fi

popd >/dev/null 2>&1
