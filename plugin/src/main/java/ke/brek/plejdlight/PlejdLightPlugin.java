package ke.brek.plejdlight;

import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.block.Block;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;

public final class PlejdLightPlugin extends JavaPlugin {
    private BridgeClient bridge;
    private BukkitTask task;

    private String configuredPlayer = "";
    private boolean invert;
    private boolean turnOffWhenOffline;
    private boolean following = true;

    private Integer desired;
    private Integer acknowledged;
    private boolean posting;
    private boolean sentOfflineOff;

    private Integer lastRawLight;
    private Integer lastPostedLight;
    private Integer heldLight;
    private String followedName = "";
    private String pauseReason = "";

    @Override
    public void onEnable() {
        saveDefaultConfig();
        configuredPlayer = getConfig().getString("player", "");
        if (configuredPlayer == null) {
            configuredPlayer = "";
        }
        configuredPlayer = configuredPlayer.strip();
        invert = getConfig().getBoolean("invert", false);
        turnOffWhenOffline = "off".equalsIgnoreCase(getConfig().getString("offline", "keep"));

        String bridgeUrl = getConfig().getString("bridge-url", "http://127.0.0.1:8765");
        if (bridgeUrl == null || bridgeUrl.isBlank()) {
            bridgeUrl = "http://127.0.0.1:8765";
        }
        bridge = new BridgeClient(bridgeUrl, getLogger());

        var command = getCommand("plejd");
        if (command == null) {
            throw new IllegalStateException("plugin.yml is missing the plejd command");
        }
        PlejdCommand executor = new PlejdCommand(this);
        command.setExecutor(executor);
        command.setTabCompleter(executor);

        long ticks = Math.max(1L, getConfig().getLong("poll-ticks", 10L));
        task = getServer().getScheduler().runTaskTimer(this, this::tick, ticks, ticks);
        getLogger().info("Plejd light link polling every " + ticks + " ticks via " + bridgeUrl);
    }

    @Override
    public void onDisable() {
        if (task != null) {
            task.cancel();
        }
        if (bridge != null) {
            bridge.close();
        }
    }

    public void sendStatus(CommandSender sender) {
        sender.sendMessage(Component.text(statusText()));
    }

    public void follow(CommandSender sender) {
        following = true;
        heldLight = null;
        acknowledged = null;
        sentOfflineOff = false;
        sender.sendMessage(Component.text("Following in-game light."));
    }

    public void holdLight(CommandSender sender, int light) {
        following = false;
        heldLight = light;
        int posted = LightScale.applyInvert(light, invert);
        want(posted);
        sender.sendMessage(Component.text(
                "Holding light " + light + " (dim " + LightScale.dimByte(posted) + "). /plejd follow resumes the game."));
    }

    private void tick() {
        try {
            sample();
        } catch (RuntimeException ex) {
            getLogger().warning("Light sample failed: " + ex.getMessage());
        }
    }

    private void sample() {
        if (!following) {
            pauseReason = "";
            return;
        }
        Player player = resolvePlayer();
        if (player == null) {
            followedName = "";
            lastRawLight = null;
            if (turnOffWhenOffline && followedPlayerIsAway() && !sentOfflineOff) {
                want(0);
                sentOfflineOff = true;
            }
            return;
        }
        sentOfflineOff = false;
        followedName = player.getName();
        pauseReason = "";
        Block block = player.getEyeLocation().getBlock();
        int raw = Math.clamp(block.getLightLevel() & 0xFF, 0, 15);
        int posted = LightScale.applyInvert(raw, invert);
        lastRawLight = raw;
        want(posted);
    }

    private Player resolvePlayer() {
        if (!configuredPlayer.isEmpty()) {
            Player exact = Bukkit.getPlayerExact(configuredPlayer);
            if (exact != null) {
                return exact;
            }
            for (Player online : Bukkit.getOnlinePlayers()) {
                if (online.getName().equalsIgnoreCase(configuredPlayer)) {
                    return online;
                }
            }
            pauseReason = configuredPlayer + " is offline";
            return null;
        }
        var online = Bukkit.getOnlinePlayers();
        if (online.size() == 1) {
            return online.iterator().next();
        }
        if (online.isEmpty()) {
            pauseReason = "nobody is online";
        } else {
            pauseReason = online.size() + " players are online; set player in config.yml";
        }
        return null;
    }

    /** True when the named player is offline, or nobody is online. Several unnamed players do not count. */
    private boolean followedPlayerIsAway() {
        if (!configuredPlayer.isEmpty()) {
            return true;
        }
        return Bukkit.getOnlinePlayers().isEmpty();
    }

    private void want(int light) {
        desired = light;
        lastPostedLight = light;
        pump();
    }

    private void pump() {
        if (posting || desired == null || desired.equals(acknowledged)) {
            return;
        }
        int sending = desired;
        posting = true;
        bridge.postLight(sending, ok -> {
            if (!isEnabled()) {
                return;
            }
            getServer().getScheduler().runTask(this, () -> {
                posting = false;
                if (ok) {
                    acknowledged = sending;
                }
                pump();
            });
        });
    }

    private String statusText() {
        String bridgeState = bridge.lastError() == null ? "bridge ok" : "bridge: " + bridge.lastError();
        String invertText = invert ? ", invert on" : "";
        if (!following) {
            int posted = heldLight == null ? 0 : LightScale.applyInvert(heldLight, invert);
            return "Plejd holding " + heldLight + " (dim " + LightScale.dimByte(posted) + ")"
                    + invertText + ", " + bridgeState;
        }
        if (followedName.isEmpty()) {
            String why = pauseReason.isEmpty() ? "no player" : pauseReason;
            String lamp = sentOfflineOff ? "sent light 0" : "lamp unchanged";
            return "Plejd paused (" + why + "), " + lamp + ", " + bridgeState;
        }
        String light = lastRawLight == null ? "n/a" : Integer.toString(lastRawLight);
        String posted = lastPostedLight == null ? "n/a" : Integer.toString(lastPostedLight);
        String dim = lastPostedLight == null ? "n/a" : Integer.toString(LightScale.dimByte(lastPostedLight));
        return "Plejd following " + followedName + ", eye light " + light
                + ", sending " + posted + " (dim " + dim + ")" + invertText + ", " + bridgeState;
    }
}
