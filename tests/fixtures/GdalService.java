// tests/fixtures/GdalService.java
package com.example.gdal;

import java.io.IOException;

@Service
public class GdalService {

    public void convert(String input, String output) throws IOException {
        ProcessBuilder pb = new ProcessBuilder(
            "gdal_translate", "-of", "GTiff", input, output
        );
        pb.start().waitFor();
    }

    public void runPython(String script) throws IOException {
        Runtime.getRuntime().exec(new String[]{"python3", script});
    }

    public void runShell(String command) throws IOException {
        ProcessBuilder pb = new ProcessBuilder("/bin/bash", "-c", command);
        pb.start();
    }
}
