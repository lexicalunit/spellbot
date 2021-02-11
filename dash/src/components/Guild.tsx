import NotFound from "components/NotFound"
import React, { useEffect } from "react"
import { Form } from "react-bootstrap"
import { useSelector } from "react-redux"
import { useParams } from "react-router-dom"
import {
  backendGuild,
  discordTokenSelector,
  guildDisplaySelector,
  guildSelector,
  loggedInSelector,
  useAppDispatch,
} from "state"
import "styles/Guild.css"

interface GuildParams {
  id: string
}

function GuildView(): React.ReactElement {
  const dispatch = useAppDispatch()
  const params = useParams<GuildParams>()
  const { id: guildId } = params
  const guild = useSelector(guildSelector(guildId))
  const loggedIn = useSelector(loggedInSelector)
  const discordToken = useSelector(discordTokenSelector)
  const guildDisplay = useSelector(guildDisplaySelector)

  useEffect(() => {
    if (!discordToken || !loggedIn) return
    dispatch(backendGuild({ discordToken, guildId }))
  }, [discordToken, loggedIn, dispatch, guildId])

  if (!guild) return <NotFound />

  if (!guildDisplay)
    return (
      <div className="main-content">
        <h1>{guild.name}</h1>
        <p>This guild is not configured to use SpellBot yet.</p>
      </div>
    )

  const handleSubmit = (event: any) => {
    console.log("event!")
    event.preventDefault()
  }

  return (
    <div className="main-content">
      <h1>{guild.name}</h1>
      <Form onSubmit={handleSubmit}>
        <ul className="settings">
          <li>
            <Form.Label>Games created:</Form.Label>
            <Form.Control
              tabIndex={-1}
              value={guildDisplay.gamesPlayed}
              disabled
              readOnly
            />
          </li>
          <li>
            <Form.Label>Server prefix</Form.Label>
            <Form.Label className="help">
              The command prefix used by SpellBot on this server.
            </Form.Label>
            <Form.Control
              id="serverPrefix"
              defaultValue={guildDisplay.serverPrefix}
            />
          </li>
          <li>
            <Form.Label>Game expriation time</Form.Label>
            <Form.Label className="help">
              Delete inactive games after this many minutes.
            </Form.Label>
            <Form.Control
              id="expireTimeMinutes"
              defaultValue={guildDisplay.expireTimeMinutes}
            />
          </li>
          <li>
            <Form.Check
              type="checkbox"
              label="Private links"
              id="privateLinks"
              defaultChecked={guildDisplay.privateLinks}
            />
            <Form.Label className="help">
              When enabled SpellTable links will only appear in direct messages.
            </Form.Label>
          </li>
          <li>
            <Form.Check
              type="checkbox"
              label="Show spectator link"
              id="showSpectateLink"
              defaultChecked={guildDisplay.showSpectateLink}
            />
            <Form.Label className="help">
              When enabled also show SpellTable spectate links for games.
            </Form.Label>
          </li>
          <li>
            <Form.Check
              type="checkbox"
              label="Power command allowed"
              id="powerEnabled"
              defaultChecked={guildDisplay.powerEnabled}
            />
            <Form.Label className="help">
              When enabled allow the{" "}
              <code>{guildDisplay.serverPrefix}power</code> command.
            </Form.Label>
          </li>
          <li>
            <Form.Check
              type="checkbox"
              label="Tags allowed"
              defaultChecked={guildDisplay.tagsEnabled}
            />
            <Form.Label className="help">
              When enabled allow the the use of <code>~tags</code>.
            </Form.Label>
          </li>
          <li>
            <Form.Check
              type="checkbox"
              label="Automatically create voice channels"
              id="voiceEnabled"
              defaultChecked={guildDisplay.voiceEnabled}
            />
            <Form.Label className="help">
              When enabled automatically create voice channels for games.
            </Form.Label>
          </li>
          <li>
            <Form.Label>MOTD</Form.Label>
            <Form.Label className="help">
              Your server&apos;s message of the day.
            </Form.Label>
            <Form.Control as="textarea" id="serverMotd">
              {guildDisplay.serverMotd}
            </Form.Control>
          </li>
          <li>
            <Form.Label>MOTD visibilty</Form.Label>
            <Form.Label className="help">
              Show the server&apos;s MOTD in text channels, direct messages, or
              both.
            </Form.Label>
            <Form.Control
              as="select"
              id="motdVisibilty"
              custom
              defaultValue={guildDisplay.motdVisibilty}
            >
              <option value="private">Only in direct messages</option>
              <option value="public">Only in text channels</option>
              <option value="both">Show in both places</option>
            </Form.Control>
          </li>
        </ul>
      </Form>
    </div>
  )
}

export default GuildView
