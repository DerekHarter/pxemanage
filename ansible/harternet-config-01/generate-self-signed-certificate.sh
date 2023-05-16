#! /bin/bash
# This script will generate a root CA certificate and private key for self signing certificates.
# If the rootCA is already detected from previous commit, it is reused.
# 
# Then the script generates a server key and certificate and signs it from the root
# certificate.  All certificates and keys are placed into the keys subdirectory.
#
# We only take the server name and domain as input parameters.  All other parameters are
# defined in the script, though we could parameterize these if needed
if [ "$#" -ne 3 ]
then
    echo "Error: not enough arguments provided"
    echo "usage: generate-self-signed-certificates servername servername.domain.priv keystorepassword"
    exit 1
fi

server_name=$1
domain=$2
keystore_pass=$3

key_dir=keys

root_name=HarterRootCA
root_key="${key_dir}/${root_name}.key"
root_crt="${key_dir}/${root_name}.crt"
root_subject="/CN=harter.priv/C=US/ST=Texas/L=Commerce/O=Harter Self Signing Root CA/emailAddress=derek@harter.pro"

server_key="${key_dir}/${server_name}.key"
server_csr="${key_dir}/${server_name}.csr"
server_crt="${key_dir}/${server_name}.crt"
server_p12="${key_dir}/${server_name}.pqk"
keystore="${key_dir}/${server_name}.jks"

csr_conf="${key_dir}/${domain}.csr.conf"
crt_conf="${key_dir}/${domain}.crt.conf"

echo "Generate certificates and keys using:"
echo "      RootCA name: ${root_name}"
echo "      server name: ${server_name}"
echo "    server domain: ${domain}"
echo "    keystore pass: ${keystore_pass}"
echo ""

# create root CA if there is not existing root CA by the given name
if [ ! -f ${root_crt} ]
then
    echo "1. Generating root certificate authority (CA) ${root_name} private key and certificate"
    openssl req -x509 \
            -sha256 -days 3650 \
            -nodes \
            -newkey rsa:2048 \
            -subj  "${root_subject}"\
            -keyout ${root_key} -out ${root_crt}
    echo ""
else
    echo "1. Detectected existing root authority CA ${root_name}, skipping generating new certificate"
    echo ""
fi

echo "2. Create ${server_name} server private key"
openssl genrsa -out ${server_key} 2048
echo ""

echo "3. Create configuration file for this certificate signing request"
cat > ${csr_conf} <<EOF
[ req ]
default_bits = 2048
prompt = no
default_md = sha256
req_extensions = req_ext
distinguished_name = dn

[ dn ]
C = US
ST = Texas
L = Commerce
O = Harter House
OU = Harter Cloud
CN = ${domain}
emailAddress = admin@${domain}

[ req_ext ]
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = ${domain}
#DNS.2 = *.harter.priv
#DNS.3 = *.consoleproxy.harter.priv

EOF
echo ""

echo "4. Generate a certificate signing request (csr) for server ${server_name} using server private key"
openssl req -new -key ${server_key} -out ${server_csr} -config ${csr_conf}
echo ""

echo "5. Create external certificate file with IMPORTANT/NEEDED properties for certificate to be self signed correctly"
cat > ${crt_conf} <<EOF

authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${domain}
#DNS.2 = *.harter.priv
#DNS.3 = *.consoleproxy.harter.priv
EOF
echo ""


echo "6. Generate SSL certificate for server ${server_name} using root CA ${root_name} to self sign"
openssl x509 -req \
    -in ${server_csr} \
    -CA ${root_crt} -CAkey ${root_key} \
    -CAcreateserial -out ${server_crt} \
    -days 3650 \
    -sha256 -extfile ${crt_conf}
echo ""

echo "7. Convert/combine the certificate and private key to pkcs12 keystore format (needed for cloudstack https server only)"
openssl pkcs12 -export \
    -in ${server_crt} \
    -inkey ${server_key} \
    -name ${server_name} \
    -passout pass:${keystore_pass} \
    -out ${server_p12}
echo ""

echo "8. Import the server key and certificate from pkcs12 file into a keystore for the cloudstack https management server"
keytool -importkeystore \
    -srckeystore ${server_p12} \
    -srcstoretype PKCS12 \
    -srcstorepass ${keystore_pass} \
    -deststorepass ${keystore_pass} \
    -destkeystore ${keystore} 
echo ""
