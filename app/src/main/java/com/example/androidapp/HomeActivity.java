package com.example.androidapp;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import android.widget.Button;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;

public class HomeActivity extends ComponentActivity {

    private ActivityResultLauncher<String> pickImageForUpload;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);

        Button btnCamera = findViewById(R.id.btnCamera);
        Button btnGallery = findViewById(R.id.btnGallery);
        Button btnUpload = findViewById(R.id.btnUpload);
        Button btnDownload = findViewById(R.id.btnDownload);

        pickImageForUpload = registerForActivityResult(
                new ActivityResultContracts.GetContent(),
                uri -> {
                    if (uri == null) {
                        Toast.makeText(this, "No image selected", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    Intent intent = new Intent(this, UploadActivity.class);
                    intent.setData(uri);
                    startActivity(intent);
                }
        );

        btnCamera.setOnClickListener(v -> {
            Intent intent = new Intent(this, MainActivity.class);
            startActivity(intent);
        });

        btnGallery.setOnClickListener(v -> {
            Intent intent = new Intent(Intent.ACTION_VIEW, MediaStore.Images.Media.EXTERNAL_CONTENT_URI);
            try {
                startActivity(intent);
            } catch (Exception e) {
                Toast.makeText(this, "No gallery app found", Toast.LENGTH_SHORT).show();
            }
        });

        btnUpload.setOnClickListener(v -> pickImageForUpload.launch("image/*"));

        btnDownload.setOnClickListener(v ->
                Toast.makeText(this, "Decode coming soon", Toast.LENGTH_SHORT).show()
        );
    }
}
