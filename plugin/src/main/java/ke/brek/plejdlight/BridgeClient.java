package ke.brek.plejdlight;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.function.Consumer;
import java.util.logging.Level;
import java.util.logging.Logger;

/** Posts light levels to the local Plejd bridge without blocking the server thread. */
public final class BridgeClient implements AutoCloseable {
    private final HttpClient http;
    private final URI levelUri;
    private final Logger logger;
    private volatile String lastError;
    private long lastWarningAt;

    public BridgeClient(String bridgeUrl, Logger logger) {
        String base = bridgeUrl.endsWith("/") ? bridgeUrl.substring(0, bridgeUrl.length() - 1) : bridgeUrl;
        this.levelUri = URI.create(base + "/level");
        this.logger = logger;
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
    }

    public String lastError() {
        return lastError;
    }

    public void postLight(int light, Consumer<Boolean> done) {
        HttpRequest request = HttpRequest.newBuilder(levelUri)
                .timeout(Duration.ofSeconds(40))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString("{\"light\":" + light + "}"))
                .build();
        http.sendAsync(request, HttpResponse.BodyHandlers.ofString())
                .whenComplete((response, error) -> {
                    boolean ok = error == null && response.statusCode() >= 200 && response.statusCode() < 300;
                    if (ok) {
                        lastError = null;
                    } else {
                        String detail = error != null
                                ? error.getMessage()
                                : "HTTP " + response.statusCode() + " " + truncate(response.body());
                        lastError = detail;
                        warn(detail);
                    }
                    done.accept(ok);
                });
    }

    private void warn(String detail) {
        long now = System.currentTimeMillis();
        if (now - lastWarningAt < 10_000L) {
            return;
        }
        lastWarningAt = now;
        logger.log(Level.WARNING, "Plejd bridge rejected a light update: {0}", detail);
    }

    private static String truncate(String body) {
        if (body == null) {
            return "";
        }
        String trimmed = body.strip();
        return trimmed.length() <= 180 ? trimmed : trimmed.substring(0, 180);
    }

    @Override
    public void close() {
        http.close();
    }
}
