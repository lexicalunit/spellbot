import {
  combineReducers,
  configureStore,
  createAsyncThunk,
  createSlice,
  MiddlewareArray,
} from "@reduxjs/toolkit"
import SpellAPIClient, { Guild, GuildResponse } from "clients/spellapi"
import { useDispatch } from "react-redux"
import reduxThunk from "redux-thunk"
import { getCookie, removeCookie, setCookie } from "tools"

// Actions
export type BakendLoginArgs = {
  discordToken: string
}

export const backendLogin = createAsyncThunk(
  "backendLogin",
  async (args: BakendLoginArgs, thunk) => {
    const { discordToken } = args
    const client = new SpellAPIClient(discordToken)
    const response = await client.login()
    if (response.status !== 200) {
      return thunk.rejectWithValue(
        `error ${response.status}: could not login to backend`
      )
    }
    return response.data
  }
)

export type BackendGuildArgs = {
  discordToken: string
  guildId: string
}

export const backendGuild = createAsyncThunk(
  "backendGuild",
  async (args: BackendGuildArgs, thunk) => {
    const { discordToken, guildId } = args
    const client = new SpellAPIClient(discordToken)
    const response = await client.guild(guildId)
    if (response.status !== 200) {
      return thunk.rejectWithValue(
        `error ${response.status}: could not login to backend`
      )
    }
    return response.data
  }
)

// Discord Slice
export type DiscordState = {
  token: string | undefined
}

const discordInitialState = (() => {
  const token = getCookie("discordToken")
  return { token }
})()

const discordSlice = createSlice({
  name: "discord",
  initialState: discordInitialState,
  reducers: {
    setDiscordToken(state, action) {
      state.token = action.payload
      setCookie("discordToken", state.token)
    },
    clearState(state) {
      state.token = undefined
      removeCookie("discordToken")
    },
  },
})

// Session Slice
export type SessionState = {
  username: string | undefined
  guilds: Guild[]
  guildDisplay: GuildResponse | undefined
}

const sessionInitialState = (() => {
  const initialState: SessionState = {
    username: undefined,
    guilds: [],
    guildDisplay: undefined,
  }
  return initialState
})()

const sessionSlice = createSlice({
  name: "session",
  initialState: sessionInitialState,
  reducers: {},
  extraReducers: (builder) => {
    builder.addCase(backendLogin.fulfilled, (state, action) => {
      state.username = action.payload.username
      state.guilds = action.payload.guilds
    })

    builder.addCase(backendGuild.fulfilled, (state, action) => {
      state.guildDisplay = action.payload
    })

    builder.addCase(backendGuild.rejected, (state) => {
      state.guildDisplay = undefined
    })
  },
})

// Guilds Slice
// const guildsAdaptor = createEntityAdapter<Guild>({
//   selectId: (guild) => guild.id,
//   sortComparer: (a, b) => a.name.localeCompare(b.name),
// })

// export type GuildsState = {
//   ids: string[]
//   entities: Record<string, Guild>
//   pending: boolean
// }

// const guildsInitialState: GuildsState = (() => {
//   const guildsJson = localStorage.getItem("discordGuilds")
//   const guildsData = guildsJson ? JSON.parse(guildsJson) : []
//   const adaptorState = guildsAdaptor.getInitialState(guildsData)
//   return { ...adaptorState, pending: false }
// })()

// const guildsSlice = createSlice({
//   name: "guilds",
//   initialState: guildsInitialState,
//   reducers: {
//     guildAdded: guildsAdaptor.addOne,
//     guildsReceived(state, action) {
//       guildsAdaptor.setAll(state, action.payload.guilds)
//     },
//   },
//   extraReducers: (builder) => {
//     builder.addCase(discordSlice.actions.clearState, (state) => {
//       guildsAdaptor.removeAll(state)
//       localStorage.removeItem("discordGuilds")
//     })
//     builder.addCase(fetchDiscordGuilds.fulfilled, (state, action) => {
//       guildsAdaptor.setAll(state, action.payload)
//       localStorage.setItem(
//         "discordGuilds",
//         JSON.stringify({ ids: state.ids, entities: state.entities })
//       )
//       state.pending = false
//     })
//     builder.addCase(fetchDiscordGuilds.pending, (state) => {
//       state.pending = true
//     })
//     builder.addCase(fetchDiscordGuilds.rejected, (state) => {
//       state.pending = false
//     })
//   },
// })

// Selectors
export const discordTokenSelector = (state: AppState): string | undefined =>
  state.discord.token
export const discordUsernameSelector = (state: AppState): string | undefined =>
  state.session.username
export const guildsSelector = (state: AppState): Guild[] => state.session.guilds
export const guildSelector = (guildId: string) => {
  return (state: AppState): Guild | undefined => {
    return state.session.guilds.find((guild: Guild) => guild.id === guildId)
  }
}
export const guildDisplaySelector = (
  state: AppState
): GuildResponse | undefined => state.session.guildDisplay
export const loggedInSelector = (state: AppState): boolean => {
  return !!state.session.username && !!state.discord.token
}

// Guilds Selectors
// export const guildsPendingSelector = (state: AppState): boolean =>
//   state.guilds.pending
// const {
//   selectById: selectGuildById,
//   selectAll: selectAllGuilds,
// } = guildsAdaptor.getSelectors()
// const getGuildsState = (state: AppState): GuildsState => state.guilds
// type GuildOutputSelector<ReturnType> = OutputSelector<
//   AppState,
//   ReturnType,
//   (res: GuildsState) => ReturnType
// >
// export const guildsSelector = createSelector(getGuildsState, (state) => {
//   return selectAllGuilds(state)
// })
// export const guildSelector = (
//   guildId: string
// ): GuildOutputSelector<Guild | undefined> => {
//   return createSelector(getGuildsState, (state) => {
//     return selectGuildById(state, guildId)
//   })
// }

// Actions
export const { setDiscordToken, clearState } = discordSlice.actions
// export const { setUsername, setGuilds } = sessionSlice.actions

// Dispatch
export type AppDispatch = typeof store.dispatch
export const useAppDispatch = (): AppDispatch => useDispatch<AppDispatch>()

const reducer = combineReducers({
  discord: discordSlice.reducer,
  // guilds: guildsSlice.reducer,
  session: sessionSlice.reducer,
})
const middleware = new MiddlewareArray().concat(reduxThunk)
const store = configureStore({ reducer, middleware })
export type AppState = ReturnType<typeof store.getState>
export default store
