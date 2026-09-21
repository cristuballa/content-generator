import os
import sys
import socket
import datetime
import ipaddress
import subprocess
from pathlib import Path
from typing import Tuple, Optional, List

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

DEFAULT_CERT_DIR = Path(__file__).resolve().parent.parent / "certs"

class CertManager:
    """Manages SSL/TLS certificates for KCT Studio local and LAN HTTPS serving."""

    @staticmethod
    def get_local_ip() -> str:
        """Determines the primary local LAN IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            # Connecting to a public IP doesn't send packets but selects the active network interface
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"

    @classmethod
    def ensure_certificates(cls, cert_dir: Optional[Path] = None) -> Tuple[Path, Path]:
        """
        Ensures SSL certificate and private key exist.
        If missing or corrupted, generates a new self-signed certificate with SANs
        for localhost, 127.0.0.1, computer hostname, and local LAN IP.
        Returns (cert_path, key_path).
        """
        target_dir = cert_dir or DEFAULT_CERT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        cert_file = target_dir / "cert.pem"
        key_file = target_dir / "key.pem"
        crt_file = target_dir / "cert.crt"

        if cert_file.exists() and key_file.exists() and cert_file.stat().st_size > 100 and key_file.stat().st_size > 100:
            if not crt_file.exists():
                crt_file.write_bytes(cert_file.read_bytes())
            return cert_file, key_file

        print(f"[CertManager] Generating new SSL/TLS certificate in {target_dir}...")

        # 1. Generate 2048-bit RSA Private Key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # 2. Build Subject & Issuer
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "KCT Studio"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "AI Content Pipeline"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])

        # 3. Subject Alternative Names (SAN)
        alt_names: List[x509.GeneralName] = [
            x509.DNSName("localhost"),
            x509.DNSName("*.localhost"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            x509.IPAddress(ipaddress.IPv4Address("0.0.0.0")),
        ]

        hostname = socket.gethostname()
        if hostname:
            try:
                alt_names.append(x509.DNSName(hostname))
            except Exception:
                pass

        local_ip = cls.get_local_ip()
        if local_ip and local_ip not in ("127.0.0.1", "0.0.0.0"):
            try:
                alt_names.append(x509.IPAddress(ipaddress.IPv4Address(local_ip)))
            except Exception:
                pass

        # 4. Certificate Details (10 years validity)
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(
                x509.SubjectAlternativeName(alt_names),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    ExtendedKeyUsageOID.SERVER_AUTH,
                    ExtendedKeyUsageOID.CLIENT_AUTH,
                ]),
                critical=False,
            )
            .sign(private_key, hashes.SHA256())
        )

        # 5. Serialize and write files
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        key_file.write_bytes(key_pem)
        cert_file.write_bytes(cert_pem)
        crt_file.write_bytes(cert_pem)

        print(f"[CertManager] SSL Certificate created: {cert_file}")
        print(f"[CertManager] SSL Private Key created: {key_file}")
        print(f"[CertManager] Windows CRT created: {crt_file}")
        return cert_file, key_file

    @classmethod
    def install_to_windows_store(cls, cert_path: Optional[Path] = None) -> bool:
        """Imports the certificate into Windows CurrentUser\\Root trust store."""
        if sys.platform != "win32":
            return False

        target = cert_path or (DEFAULT_CERT_DIR / "cert.crt")
        if not target.exists():
            return False

        try:
            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                f"Import-Certificate -FilePath '{str(target.resolve())}' -CertStoreLocation Cert:\\CurrentUser\\Root"
            ]
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=creationflags)
            if res.returncode == 0:
                print(f"[CertManager] Certificate successfully trusted in Windows CurrentUser\\Root")
                return True
            else:
                print(f"[CertManager] Failed to install certificate: {res.stderr}")
                return False
        except Exception as e:
            print(f"[CertManager] Error installing certificate to Windows store: {e}")
            return False

cert_manager = CertManager()
