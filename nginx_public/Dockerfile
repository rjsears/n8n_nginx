# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /nginx_public/Dockerfile
#
# Part of the "n8n_nginx/n8n_management" suite
#
# Public website nginx. Stock nginx plus an "fbuser" account with the same
# uid as File Browser (1000), so the workers (nginx-public.conf: "user
# fbuser;") can read the files uploaded through File Browser.
# This is the entire source of the former rjsears/nginx-public image.
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

FROM nginx:1.30.5-alpine

RUN adduser -D -u 1000 fbuser
