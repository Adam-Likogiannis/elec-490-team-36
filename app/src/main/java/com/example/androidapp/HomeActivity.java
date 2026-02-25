package com.example.androidapp;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Button;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;

public class HomeActivity extends ComponentActivity {

    private ActivityResultLauncher<Intent> pickImageForView;
    private ActivityResultLauncher<String> pickImageForUpload;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_home);

        Button btnCamera = findViewById(R.id.btnCamera);
        Button btnGallery = findViewById(R.id.btnGallery);
        Button btnUpload = findViewById(R.id.btnUpload);
        Button btnDownload = findViewById(R.id.btnDownload);

        pickImageForView = registerForActivityResult(
                new ActivityResultContracts.StartActivityForResult(),
                result -> {
                    if (result.getResultCode() != RESULT_OK || result.getData() == null) {
                        return;
                    }
                    Uri uri = result.getData().getData();
                    if (uri == null) {
                        return;
                    }

                    Intent viewIntent = new Intent(Intent.ACTION_VIEW);
                    viewIntent.setDataAndType(uri, "image/*");
                    viewIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);

                    try {
                        startActivity(viewIntent);
                    } catch (Exception ignored) {
                    }
                }
        );

        pickImageForUpload = registerForActivityResult(
                new ActivityResultContracts.GetContent(),
                uri -> {
                    if (uri == null) {
                        return;
                    }
                    Intent intent = new Intent(this, UploadActivity.class);
                    intent.setData(uri);
                    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    startActivity(intent);
                }
        );

        btnCamera.setOnClickListener(v -> {
            Intent intent = new Intent(this, MainActivity.class);
            startActivity(intent);
        });

        btnGallery.setOnClickListener(v -> {
            Intent pickIntent = new Intent(Intent.ACTION_PICK);
            pickIntent.setType("image/*");
            pickImageForView.launch(pickIntent);
        });

        btnUpload.setOnClickListener(v -> pickImageForUpload.launch("image/*"));

        btnDownload.setOnClickListener(v ->
                Toast.makeText(this, "Decode coming soon", Toast.LENGTH_SHORT).show()
        );
    }
}