package com.example.androidapp;

import android.Manifest;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.MediaStore;
import android.widget.Button;
import android.widget.ImageButton;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageCapture;
import androidx.camera.core.ImageCaptureException;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;

import com.google.common.util.concurrent.ListenableFuture;

import java.text.SimpleDateFormat;
import java.util.Locale;
import java.util.concurrent.ExecutionException;

public class MainActivity extends ComponentActivity {

    private PreviewView previewView;
    private Button btnCapture;
    private Button btnSwitch;
    private ImageButton btnBack;

    private ImageCapture imageCapture = null;
    private CameraSelector cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA;

    private final ActivityResultLauncher<String> requestCamera =
            registerForActivityResult(new ActivityResultContracts.RequestPermission(), granted -> {
                if (granted) {
                    startCamera();
                } else {
                    Toast.makeText(this, "Camera permission is required.", Toast.LENGTH_SHORT).show();
                    finish();
                }
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_camera);

        previewView = findViewById(R.id.previewView);
        btnCapture = findViewById(R.id.btnCapture);
        btnSwitch = findViewById(R.id.btnSwitch);
        btnBack = findViewById(R.id.btnBack);

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED) {
            startCamera();
        } else {
            requestCamera.launch(Manifest.permission.CAMERA);
        }

        btnCapture.setOnClickListener(v -> takePhoto());

        btnSwitch.setOnClickListener(v -> {
            cameraSelector =
                    (cameraSelector == CameraSelector.DEFAULT_BACK_CAMERA)
                            ? CameraSelector.DEFAULT_FRONT_CAMERA
                            : CameraSelector.DEFAULT_BACK_CAMERA;
            startCamera();
        });


        btnBack.setOnClickListener(v -> {
            Intent intent = new Intent(MainActivity.this, HomeActivity.class);
            startActivity(intent);
            finish();
        });
    }

    private void startCamera() {
        ListenableFuture<ProcessCameraProvider> cameraProviderFuture =
                ProcessCameraProvider.getInstance(this);

        cameraProviderFuture.addListener(() -> {
            try {
                ProcessCameraProvider cameraProvider = cameraProviderFuture.get();

                Preview preview = new Preview.Builder().build();
                preview.setSurfaceProvider(previewView.getSurfaceProvider());

                imageCapture = new ImageCapture.Builder()
                        .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                        .build();

                cameraProvider.unbindAll();
                cameraProvider.bindToLifecycle(this, cameraSelector, preview, imageCapture);

            } catch (ExecutionException | InterruptedException e) {
                Toast.makeText(this, "Failed to start camera: " + e.getMessage(),
                        Toast.LENGTH_SHORT).show();
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void takePhoto() {
        if (imageCapture == null) return;

        String name = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US)
                .format(System.currentTimeMillis());

        ContentValues values = new ContentValues();
        values.put(MediaStore.MediaColumns.DISPLAY_NAME, "IMG_" + name);
        values.put(MediaStore.MediaColumns.MIME_TYPE, "image/jpeg");

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            values.put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/CameraX");
        }

        ImageCapture.OutputFileOptions output = new ImageCapture.OutputFileOptions.Builder(
                getContentResolver(),
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                values
        ).build();

        imageCapture.takePicture(
                output,
                ContextCompat.getMainExecutor(this),
                new ImageCapture.OnImageSavedCallback() {

                    @Override
                    public void onError(ImageCaptureException exc) {
                        Toast.makeText(MainActivity.this,
                                "Failed to save: " + exc.getMessage(),
                                Toast.LENGTH_SHORT).show();
                    }

                    @Override
                    public void onImageSaved(ImageCapture.OutputFileResults outputFileResults) {
                        Toast.makeText(MainActivity.this,
                                "Saved to gallery",
                                Toast.LENGTH_SHORT).show();
                    }
                }
        );
    }
}
