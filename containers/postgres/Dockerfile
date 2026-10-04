FROM postgres:18.6-trixie@sha256:5a5a84b19854a9ffaa54082c166ff4ec27473a361e496e5ea167f298f2da9722

USER root
COPY requirements.txt /opt/patroni-requirements.txt
RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends python3-venv python3-psycopg2 ca-certificates pgbackrest \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv --system-site-packages /opt/patroni \
    && /opt/patroni/bin/pip install --no-cache-dir -r /opt/patroni-requirements.txt \
    && /opt/patroni/bin/pip check \
    && /opt/patroni/bin/python -c 'import psycopg2; import patroni.dcs.etcd3' \
    && /opt/patroni/bin/patroni --version \
    && pgbackrest version \
    && mkdir -p /ha-data /etc/pgbackrest /var/log/pgbackrest /var/spool/pgbackrest \
    && chown -R postgres:postgres /ha-data /etc/pgbackrest /var/log/pgbackrest /var/spool/pgbackrest

ENV PATH="/opt/patroni/bin:${PATH}"
USER postgres
ENTRYPOINT ["/opt/patroni/bin/patroni", "/etc/patroni.yml"]
