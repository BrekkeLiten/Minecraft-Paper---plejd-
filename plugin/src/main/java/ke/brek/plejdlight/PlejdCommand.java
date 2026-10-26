package ke.brek.plejdlight;

import java.util.List;
import java.util.Locale;
import net.kyori.adventure.text.Component;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

public final class PlejdCommand implements CommandExecutor, TabCompleter {
    private final PlejdLightPlugin plugin;

    public PlejdCommand(PlejdLightPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(
            @NotNull CommandSender sender,
            @NotNull Command command,
            @NotNull String label,
            @NotNull String[] args) {
        if (!sender.hasPermission("plejd.use")) {
            sender.sendMessage(Component.text("You cannot use /plejd."));
            return true;
        }
        if (args.length == 0 || args[0].equalsIgnoreCase("status")) {
            plugin.sendStatus(sender);
            return true;
        }
        if (args[0].equalsIgnoreCase("follow")) {
            plugin.follow(sender);
            return true;
        }
        if (args[0].equalsIgnoreCase("set")) {
            if (args.length < 2) {
                sender.sendMessage(Component.text("Usage: /plejd set <0-15>"));
                return true;
            }
            try {
                int light = Integer.parseInt(args[1]);
                if (light < 0 || light > 15) {
                    sender.sendMessage(Component.text("Light must be 0..15."));
                    return true;
                }
                plugin.holdLight(sender, light);
            } catch (NumberFormatException ex) {
                sender.sendMessage(Component.text("Light must be 0..15."));
            }
            return true;
        }
        sender.sendMessage(Component.text("Usage: /plejd <status|set <0-15>|follow>"));
        return true;
    }

    @Override
    public @Nullable List<String> onTabComplete(
            @NotNull CommandSender sender,
            @NotNull Command command,
            @NotNull String alias,
            @NotNull String[] args) {
        if (!sender.hasPermission("plejd.use")) {
            return List.of();
        }
        if (args.length == 1) {
            return filter(List.of("status", "set", "follow"), args[0]);
        }
        if (args.length == 2 && args[0].equalsIgnoreCase("set")) {
            return filter(List.of("0", "7", "15"), args[1]);
        }
        return List.of();
    }

    private static List<String> filter(List<String> options, String prefix) {
        String needle = prefix.toLowerCase(Locale.ROOT);
        return options.stream().filter(option -> option.startsWith(needle)).toList();
    }
}
