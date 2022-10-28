# Deployment

SpellBot is deplyed to [Heroku][heroku] using container deployments using
the script at `scripts/deploy.sh`.

Below is a script for deploying SpellBot to Heroku. You can also use the `publish.sh`
script included in this repository rather than running these manually.

```shell
# You have to be logged into the Heroku container registry
docker login
heroku login
heroku container:login

APP="<the name of your heroku app>"

docker build -t "registry.heroku.com/$APP/web" .
docker push "registry.heroku.com/$APP/web"
heroku container:release web --app $APP
```

## Datadog

Traces and logs can be found in [Datadog][datadog].

### Datadog & Heroku - Logs

Logs from heroku are sent to datadog via a drain. This was set up using the
[Collect Heroku logs][collect-logs] guide. The relevent command is as follows.
The URL in the command has been broken up into multiple lines for ease of
reading, but should be ran part of a one line unbroken command.

```shell
heroku drains:add -a <APPLICATION_NAME> \
    'https://http-intake.logs.datadoghq.com/api/v2/logs/
     ?dd-api-key=<DD_API_KEY>
     &ddsource=heroku
     &env=<ENV>
     &service=<SERVICE>
     &host=<HOST>'
```

[collect-logs]: https://docs.datadoghq.com/logs/guide/collect-heroku-logs/
[datadog]: https://app.datadoghq.com/apm/home
[heroku]: https://dashboard.heroku.com/apps/lexicalunit-spellbot
