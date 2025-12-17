from python_freeipa import Client
from app.config import CONFIG, logger
from typing import Tuple
import datetime
import random
import dns.resolver

def ipa_resolve_srv(service: str, protocol: str, domain: str) -> Optional[Tuple[str, int]]:
    """
    Resolves SRV records and returns the highest priority (best) server.

    Args:
        service: The service name (e.g., "_ldap")
        protocol: The protocol (e.g., "_tcp")
        domain: The domain name (e.g., "example.com")

    Returns:
        Tuple of (target_host, port) for the best server, or None if no records found.
        Target_host is returned as a string without trailing dot.
    """
    query_name = f"{service}.{protocol}.{domain}"

    try:
        answers = dns.resolver.resolve(query_name, 'SRV')

        if not answers:
            logger.info(f"No SRV records found for {query_name}")
            return None

        # Group records by priority
        records_by_priority = {}
        for rdata in answers:
            prio = rdata.priority
            if prio not in records_by_priority:
                records_by_priority[prio] = []
            records_by_priority[prio].append((rdata.weight, rdata.target.to_text().rstrip('.'), rdata.port))

        # Get the lowest (best) priority
        best_priority = min(records_by_priority.keys())
        candidates = records_by_priority[best_priority]

        if not candidates:
            return None

        # If only one candidate, return it
        if len(candidates) == 1:
            weight, target, port = candidates[0]
            logger.info(f"Selected SRV (priority {best_priority}): {target}:{port}")
            return target, port

        # Multiple candidates at same priority: use weight-based selection
        total_weight = sum(weight for weight, _, _ in candidates)
        if total_weight == 0:
            # All weights zero → pick randomly
            selected = random.choice(candidates)
        else:
            # Weighted random selection
            rand = random.randint(1, total_weight)
            cumulative = 0
            for weight, target, port in candidates:
                cumulative += weight
                if rand <= cumulative:
                    selected = (weight, target, port)
                    break
            else:
                selected = candidates[-1]  # Fallback

        _, target, port = selected
        logger.info(f"Selected SRV (priority {best_priority}, weighted): {target}:{port}")
        return target, port

    except dns.resolver.NoAnswer:
        logger.info(f"No SRV records found for {query_name}")
        return None
    except dns.resolver.NXDOMAIN:
        logger.info(f"Domain {domain} does not exist")
        return None
    except Exception as e:
        logger.info(f"An error occurred during SRV lookup: {e}")
        return None

def get_ipa_client():
    """
    Creates and returns an authenticated IPA Client instance.

    Raises:
        RuntimeError: If no Kerberos SRV records are found or resolution fails.
    """
    host, _ = ipa_resolve_srv("_kerberos", "_tcp", CONFIG["domain"])

    if host is None:
        raise RuntimeError(
            f"Failed to discover FreeIPA server: "
            f"No _kerberos._tcp.{CONFIG['domain']} SRV records found. "
            f"Check DNS configuration or domain setting."
        )

    logger.info(f"Connecting to FreeIPA server: {host}")

    try:
        c = Client(host=host, verify_ssl=CONFIG["IPA_VERIFY_SSL"])
        c.login(CONFIG["IPA_USER"], CONFIG["IPA_PASS"])
        logger.info("Successfully authenticated to FreeIPA")
        return c
    except Exception as e:
        raise RuntimeError(f"Failed to authenticate to FreeIPA server {host}: {e}") from e

# --- Helper: Robust Command Executor ---
def execute_ipa_command(client, command, *args, **kwargs):
    try:
        if hasattr(client, command):
            return getattr(client, command)(*args, **kwargs)
        return getattr(client, command)(*args, **kwargs)
    except AttributeError:
        return client._request(command, list(args), kwargs)


# --- Action: Add Host to IPA ---
def ipa_host_add(vm_name: str, namespace: str, vm_uuid: str) -> str:
    client_ipa = get_ipa_client()
    fqdn = build_fqdn(vm_name, namespace)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    desc_text = f"Created by virt-joiner at {timestamp} | K8s UID: {vm_uuid}"

    logger.info(f"Registering host: {fqdn}")
    try:
        execute_ipa_command(
            client_ipa, "host_add", fqdn, force=True, description=desc_text
        )
        otp = vm_uuid
        execute_ipa_command(client_ipa, "host_mod", fqdn, userpassword=otp)
        return otp
    except Exception as e:
        logger.error(f"IPA Add Error for {fqdn}: {e}")
        raise e


# --- Action: Delete Host from IPA ---
def ipa_host_del(vm_name: str, namespace: str):
    client_ipa = get_ipa_client()
    fqdn = build_fqdn(vm_name, namespace)
    logger.info(f"Deleting host: {fqdn}")
    try:
        execute_ipa_command(client_ipa, "host_del", fqdn)
    except Exception as e:
        if "not found" in str(e).lower():
            logger.info(f"Host {fqdn} already gone.")
            return
        logger.error(f"IPA Del Error for {fqdn}: {e}")
        raise e


# --- Helper: FQDN Construction ---
def build_fqdn(vm_name: str, namespace: str) -> str:
    return f"{vm_name}.{namespace}.{CONFIG['DOMAIN']}"
