#!/usr/bin/env python3
import distro

import funct
import sql

from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('templates/'), autoescape=True)
template = env.get_template('hapservers.html')

print('Content-type: text/html\n')
funct.check_login()
services = []
servers: object
user, user_id, role, token, servers, user_services = funct.get_users_params()

form = funct.form
serv = funct.is_ip_or_dns(form.getvalue('serv'))
service = funct.checkAjaxInput(form.getvalue('service'))
autorefresh = 0
servers_waf = ()
title = "HAProxy servers overview"
cmd = "ps ax |grep -e 'keep_alive.py' |grep -v grep |wc -l"
keep_alive, stderr = funct.subprocess_execute(cmd)
is_restart = ''
restart_settings = ''

if service in ('haproxy', 'nginx', 'keepalived', 'apache'):
    service_desc = sql.select_service(service)
    if funct.check_login(service=service_desc.service_id):
        title = f'{service_desc.service} servers overview'
        if serv:
            if funct.check_is_server_in_group(serv):
                servers = sql.select_servers(server=serv)
                autorefresh = 1
                server_id = sql.select_server_id_by_ip(serv)
                docker_settings = sql.select_docker_service_settings(server_id, service_desc.slug)
                restart_settings = sql.select_restart_service_settings(server_id, service_desc.slug)
        else:
            servers = sql.get_dick_permit(virt=1, service=service_desc.slug)
            docker_settings = sql.select_docker_services_settings(service_desc.slug)
            restart_settings = sql.select_restart_services_settings(service_desc.slug)
else:
    print('<meta http-equiv="refresh" content="0; url=/app/overview.py">')

services_name = {'roxy-wi-checker': 'Master backends checker service',
                 'roxy-wi-keep_alive': 'Auto start service',
                 'roxy-wi-metrics': 'Master metrics service'}
for s, v in services_name.items():
    if distro.id() == 'ubuntu':
        if s == 'roxy-wi-keep_alive':
            s = 'roxy-wi-keep-alive'
        cmd = "apt list --installed 2>&1 |grep " + s
    else:
        cmd = "rpm --query " + s + "-* |awk -F\"" + s + "\" '{print $2}' |awk -F\".noa\" '{print $1}' |sed 's/-//1' |sed 's/-/./'"
    service_ver, stderr = funct.subprocess_execute(cmd)
    try:
        services.append([s, service_ver[0]])
    except Exception:
        services.append([s, ''])

haproxy_sock_port = sql.get_setting('haproxy_sock_port')
servers_with_status1 = []
out1 = ''
if len(servers) == 1:
    serv = servers[0][2]
for s in servers:
    servers_with_status = list()
    servers_with_status.append(s[0])
    servers_with_status.append(s[1])
    servers_with_status.append(s[2])
    servers_with_status.append(s[11])
    if service == 'nginx':
        h = (['', ''],)
        cmd = [
            "/usr/sbin/nginx -v 2>&1|awk '{print $3}' && systemctl status nginx |grep -e 'Active' |awk "
            "'{print $2, $9$10$11$12$13}' && ps ax |grep nginx:|grep -v grep |wc -l"]
        for service_set in docker_settings:
            if service_set.server_id == s[0] and service_set.setting == 'dockerized' and service_set.value == '1':
                container_name = sql.get_setting('nginx_container_name')
                cmd = [
                    "docker exec -it " + container_name + " /usr/sbin/nginx -v 2>&1|awk '{print $3}' && "
                    "docker ps -a -f name=" + container_name + " --format '{{.Status}}'|tail -1 && ps ax |grep nginx:"
                    "|grep -v grep |wc -l"
                ]
        try:
            out = funct.ssh_command(s[2], cmd)
            h = ()
            out1 = []
            for k in out.split():
                out1.append(k)
            h = (out1,)
            servers_with_status.append(h)
            servers_with_status.append(h)
            servers_with_status.append(s[17])
        except Exception:
            servers_with_status.append(h)
            servers_with_status.append(h)
            servers_with_status.append(s[17])
    elif service == 'keepalived':
        h = (['', ''],)
        cmd = [
            "/usr/sbin/keepalived -v 2>&1|head -1|awk '{print $2}' && systemctl status keepalived |"
            "grep -e 'Active' |awk '{print $2, $9$10$11$12$13}' && ps ax |grep keepalived|grep -v grep |wc -l"
        ]
        try:
            out = funct.ssh_command(s[2], cmd)
            out1 = []
            for k in out.split():
                out1.append(k)
            h = (out1,)
            servers_with_status.append(h)
            servers_with_status.append(h)
            servers_with_status.append(s[22])
        except Exception:
            servers_with_status.append(h)
            servers_with_status.append(h)
            servers_with_status.append(s[22])
    elif service == 'apache':
        h = (['', ''],)
        apache_stats_user = sql.get_setting('apache_stats_user')
        apache_stats_password = sql.get_setting('apache_stats_password')
        apache_stats_port = sql.get_setting('apache_stats_port')
        apache_stats_page = sql.get_setting('apache_stats_page')
        cmd = "curl -s -u %s:%s http://%s:%s/%s?auto |grep 'ServerVersion\|Processes\|ServerUptime:'" % (
            apache_stats_user, apache_stats_password, s[2], apache_stats_port, apache_stats_page
        )
        try:
            out = funct.subprocess_execute(cmd)
            if out != '':
                for k in out:
                    servers_with_status.append(k)
                servers_with_status.append(s[22])
        except Exception:
            servers_with_status.append(h)
            servers_with_status.append(h)
            servers_with_status.append(s[22])
    else:
        cmd = 'echo "show info" |nc %s %s -w 1 -v|grep -e "Ver\|Uptime:\|Process_num"' % (s[2], haproxy_sock_port)
        out = funct.subprocess_execute(cmd)
        for k in out:
            if "Connection refused" not in k:
                out1 = out
            else:
                out1 = False
            servers_with_status.append(out1)

        servers_with_status.append(s[12])

    servers_with_status.append(sql.is_master(s[2]))
    servers_with_status.append(sql.select_servers(server=s[2]))

    is_keepalived = sql.select_keepalived(s[2])

    if is_keepalived:
        try:
            cmd = ['sudo kill -USR1 `cat /var/run/keepalived.pid` && sudo grep State /tmp/keepalived.data -m 1 |'
                   'awk -F"=" \'{print $2}\'|tr -d \'[:space:]\' && sudo rm -f /tmp/keepalived.data']
            out = funct.ssh_command(s[2], cmd)
            out1 = ('1', out)
            servers_with_status.append(out1)
        except Exception:
            servers_with_status.append('')
    else:
        servers_with_status.append('')

    servers_with_status1.append(servers_with_status)

try:
    user_status, user_plan = funct.return_user_status()
except Exception as e:
    user_status, user_plan = 0, 0
    funct.logging('localhost', 'Cannot get a user plan: ' + str(e), haproxywi=1)

template = template.render(
    h2=1, autorefresh=autorefresh, title=title, role=role, user=user, servers=servers_with_status1,
    keep_alive=''.join(keep_alive), serv=serv, service=service, services=services, user_services=user_services,
    docker_settings=docker_settings, user_status=user_status, user_plan=user_plan, servers_waf=servers_waf,
    restart_settings=restart_settings, token=token
)
print(template)
